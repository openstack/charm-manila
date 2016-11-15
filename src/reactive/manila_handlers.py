# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# this is just for the reactive handlers and calls into the charm.
from __future__ import absolute_import

import charms.reactive
import charms_openstack.charm

# This charm's library contains all of the handler code associated with
# manila -- we need to import it to get the definitions for the charm.
import charm.openstack.manila  # noqa


# Use the charms.openstack defaults for common states and hooks
charms_openstack.charm.use_defaults(
    'charm.installed',
    'amqp.connected',
    'shared-db.connected',
    # 'identity-service.connected',
    'identity-service.available',  # enables SSL support
    # 'config.changed',
    # 'update-status'
)


@charms.reactive.when('identity-service.connected')
def register_endpoints(keystone):
    """Register the endpoints when the identity-service connects.
    Note that this charm doesn't use the default endpoint registration function
    as it needs to register multiple endpoints, and thus needs a custom
    function in the charm.
    """
    with charms_openstack.charm.provide_charm_instance() as manila_charm:
        manila_charm.register_endpoints(keystone)
        manila_charm.assess_status()


@charms.reactive.when('identity-service.connected',
                      'manila-plugin.connected')
def share_to_manila_plugins_auth(keystone, manila_plugin):
    """When we have the identity-service and (a) backend plugin, share the auth
    plugin with the back end.

    TODO: if we have multiple manila-plugin's does this get called for each
    relation that gets connected?
    """
    data = {
        'username': keystone.service_username(),
        'password': keystone.service_password(),
        'project_domain_id': 'default',
        'project_name': 'services',
        'user_domain_id': 'default',
        'auth_uri': ("{protocol}://{host}:{port}"
                     .format(protocol=keystone.service_protocol(),
                             host=keystone.service_host(),
                             port=keystone.service_port())),
        'auth_url': ("{protocol}://{host}:{port}"
                     .format(protocol=keystone.auth_protocol(),
                             host=keystone.auth_host(),
                             port=keystone.auth_port())),
        'auth_type': 'password',
    }
    # Set the auth data to be the same for all plugins
    manila_plugin.set_authentication_data(data)


@charms.reactive.when('shared-db.available',
                      'manila.config.rendered')
def maybe_do_syncdb(shared_db):
    """Sync the database when the shared-db becomes available.  Note that the
    charms.openstack.OpenStackCharm.db_sync() default method checks that only
    the leader does the sync.  As manila uses alembic to do the database
    migration, it doesn't matter if it's done more than once, so we don't have
    to gate it in the charm.
    """
    with charms_openstack.charm.provide_charm_instance() as manila_charm:
        manila_charm.db_sync()


@charms.reactive.when('shared-db.available',
                      'identity-service.available',
                      'amqp.available')
def render_stuff(*args):
    """Render the configuration for Manila when all the interfaces are
    available.
    """
    with charms_openstack.charm.provide_charm_instance() as manila_charm:
        manila_charm.render_with_interfaces(args)
        manila_charm.assess_status()
        charms.reactive.set_state('manila.config.rendered')


@charms.reactive.when('config.changed',
                      'shared-db.available',
                      'identity-service.available',
                      'amqp.available')
def config_changed(*args):
    """When the configuration is changed, check that we have all the interfaces
    and then re-render all the configuration files.  Note that this means that
    the configuration files won't be written until all the interfaces are
    available and STAY available.
    """
    render_stuff(*args)
