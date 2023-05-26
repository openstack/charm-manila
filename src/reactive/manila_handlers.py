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

import charmhelpers.contrib.openstack.utils as os_utils
import charmhelpers.core.host as ch_host

import charms.reactive
import charms.reactive.relations as relations
import charms_openstack.bus
import charms_openstack.charm

charms_openstack.bus.discover()


# Use the charms.openstack defaults for common states and hooks
charms_openstack.charm.use_defaults(
    'amqp.connected',
    'certificates.available',
    'charm.installed',
    'cluster.available',
    'config.rendered',
    'shared-db.connected',
    'upgrade-charm',
    'certificates.available',
    'cluster.available',
    'config.changed',
    'update-status',
)


@charms.reactive.when('identity-service.connected')
@charms.reactive.when_not('identity-service.available')
def register_endpoints(keystone):
    """Register the endpoints when the identity-service connects.
    Note that this charm doesn't use the default endpoint registration function
    as it needs to register multiple endpoints, and thus needs a custom
    function in the charm.
    """
    with charms_openstack.charm.provide_charm_instance() as manila_charm:
        manila_charm.register_endpoints(keystone)
        manila_charm.assess_status()


@charms.reactive.when('identity-service.connected')
@charms.reactive.when_any('manila-plugin.connected',
                          'remote-manila-plugin.connected')
def share_to_manila_plugins_auth():
    """When we have the identity-service and (a) backend plugin, share the auth
    plugin with the back end.

    Note that the interface deals with ensurign that each plugin gets the same
    data.
    """
    keystone = charms.reactive.endpoint_from_flag('identity-service.connected')
    manila_plugins = [
        relations.endpoint_from_flag('manila-plugin.connected'),
        relations.endpoint_from_flag('remote-manila-plugin.connected')
    ]

    data = {
        'username': keystone.service_username(),
        'password': keystone.service_password(),
        'project_domain_name': keystone.service_domain(),
        'project_name': 'services',
        'user_domain_name': keystone.service_domain(),
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
    for manila_plugin in manila_plugins:
        if manila_plugin is not None:
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
    charms.reactive.set_state('db.synced')


@charms.reactive.when('shared-db.available',
                      'identity-service.available',
                      'amqp.available')
def render_stuff(*args):
    """Render the configuration for Manila when all the interfaces are
    available.

    Note that the charm class actually calls on the manila-plugin directly to
    get the config, so we unconditionally clear the changed status here, if it
    was set.
    """
    with charms_openstack.charm.provide_charm_instance() as manila_charm:
        pre_ssl_enabled = manila_charm.get_state('ssl.enabled')
        tls = relations.endpoint_from_flag('certificates.available')
        manila_charm.configure_tls(certificates_interface=tls)
        if pre_ssl_enabled != manila_charm.get_state('ssl.enabled'):
            keystone = relations.endpoint_from_flag(
                'identity-service.available')
            manila_charm.register_endpoints(keystone)

        manila_charm.render_with_interfaces(args)
        manila_charm.assess_status()
        charms.reactive.set_state('manila.config.rendered')
        for manila_plugin in [
            relations.endpoint_from_flag('manila-plugin.changed'),
            relations.endpoint_from_flag('remote-manila-plugin.changed')
        ]:
            if manila_plugin is not None:
                manila_plugin.clear_changed()
        manila_charm.enable_webserver_site()


@charms.reactive.when('shared-db.available',
                      'identity-service.available',
                      'amqp.available')
@charms.reactive.when_any('config-changed',
                          'manila-plugin.changed',
                          'remote-manila-plugin.changed')
def config_changed(*args):
    """When the configuration is changed, check that we have all the interfaces
    and then re-render all the configuration files.  Note that this means that
    the configuration files won't be written until all the interfaces are
    available and STAY available.
    """
    render_stuff(*args)


@charms.reactive.hook('update-status')
def update_status():
    """Use the update-status hook to check to see if we can restart the
    manila-share service: (BUG#1706699).  The bug appears to be a race-hazard
    but it's proving very difficult to track it down.

    This is a band-aid to enable the charm to get into a working state once all
    of the interfaces have joined, and the bug has been hit; otherwise the
    charm stays "stuck" with the service not running.

    Note, there is no need to actually call update_status as one of the other
    handlers will activate it.
    """
    if not os_utils.is_unit_paused_set():
        with charms_openstack.charm.provide_charm_instance() as manila_charm:
            if manila_charm.get_adapter('manila-plugin.connected'):
                services = ['manila-share']
            else:
                services = []
        state, message = os_utils._ows_check_services_running(
            services=services,
            ports=None)
        if state == 'blocked' and services:
            # try to start the 'manila-share' service
            ch_host.service_start('manila-share')


@charms.reactive.when('db.synced', 'manila.config.rendered')
@charms.reactive.when_not('config.rendered')
def config_rendered():
    """Set the config.rendered state when ready for operation.

    The config.rendered flag is used by the default handlers in
    charms.openstack to enable / disable services based on the
    readiness of the deployment. The Manila charm is using this
    functionalty to ensure that the Manila services start up only
    after the database has been synced to remove a race condition
    where the services won't restart after failing several times
    with missing migrations.
    """
    charms.reactive.set_state('config.rendered')


@charms.reactive.when('ha.connected')
def cluster_connected(hacluster):
    """Configure HA resources in corosync"""
    with charms_openstack.charm.provide_charm_instance() as manila_charm:
        manila_charm.configure_ha_resources(hacluster)
        manila_charm.assess_status()


@charms.reactive.when_none('charm.paused', 'is-update-status-hook')
@charms.reactive.when('config.rendered')
@charms.reactive.when_any('config.changed.nagios_context',
                          'config.changed.nagios_servicegroups',
                          'endpoint.nrpe-external-master.changed',
                          'nrpe-external-master.available')
def configure_nrpe():
    """Handle config-changed for NRPE options."""
    with charms_openstack.charm.provide_charm_instance() as manila_charm:
        manila_charm.render_nrpe_checks()
