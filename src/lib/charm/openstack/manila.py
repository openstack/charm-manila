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
# The manila handlers class

# bare functions are provided to the reactive handlers to perform the functions
# needed on the class.

import collections
import os
import re
import subprocess

import charmhelpers.core.host as host
import charms_openstack.charm
import charms_openstack.adapters
import charms_openstack.ip as os_ip

# note that manila-common is pulled in via the other packages.
PACKAGES = ['manila-api',
            'manila-data',
            'manila-scheduler',
            'manila-share',
            'python-pymysql',
            'python-apt',  # for subordinate neutron-openvswitch if needed.
            'apache2',
            'libapache2-mod-wsgi',
            ]

MANILA_DIR = '/etc/manila/'
MANILA_CONF = MANILA_DIR + "manila.conf"
MANILA_LOGGING_CONF = MANILA_DIR + "logging.conf"
MANILA_API_PASTE_CONF = MANILA_DIR + "api-paste.ini"
MANILA_WEBSERVER_SITE = 'manila-api'
MANILA_WSGI_CONF = '/etc/apache2/sites-available/manila-api.conf'

# select the default release function and ssl feature
charms_openstack.charm.use_defaults('charm.default-select-release')


def strip_join(s, divider=" "):
    """Cleanup the string passed, split on whitespace and then rejoin it
    cleanly

    :param s: A sting to cleanup, remove non alpha chars and then represent the
        string.
    :param divider: The joining string to put the bits back together again.
    :returns: string
    """
    return divider.join(
        re.split(r'\s+', re.sub(r'([^\s\w-])+', '', (s or ""))))


###
# Compute some options to help with template rendering
@charms_openstack.adapters.config_property
def computed_share_backends(config):
    """Determine the backend protocols that are provided as a string.

    This asks the charm class what the backend protocols are, and then provides
    it as a space separated list of backends.

    :param config: the config option on which to look up config options
    :returns: string
    """
    return ' '.join(config.charm_instance.configured_backends)


@charms_openstack.adapters.config_property
def computed_share_protocols(config):
    """Return a list of protocols as a comma (no space) separated list.
    The default protocols are CIFS,NFS.

    :param config: the config option on which to look up config options
    :returns: string
    """
    return strip_join(config.share_protocols, ',').upper()


@charms_openstack.adapters.config_property
def computed_backend_lines_manila_conf(config):
    """Return the list of lines from the backends that need to go into the
    various configuration files.

    This one is for manila.conf
    :returns list of lines: the config for the manila.conf file
    """
    return config.charm_instance.config_lines_for(MANILA_CONF)


@charms_openstack.adapters.config_property
def computed_debug_level(config):
    """Return NONE, INFO, WARNING, DEBUG depending on the settings of
    options.debug and options.level
    :returns: string, NONE, WARNING, DEBUG
    """
    if not config.debug:
        return "NONE"
    if config.verbose:
        return "DEBUG"
    return "WARNING"


class TransportURLAdapter(charms_openstack.adapters.RabbitMQRelationAdapter):
    """Add Transport URL to RabbitMQRelationAdapter
    TODO: Move to charms.openstack.adapters
    """

    DEFAULT_PORT = '5672'

    def __init__(self, relation):
        super(TransportURLAdapter, self).__init__(relation)
        self.transport_url

    @property
    def transport_url(self):
        """Return the transport URL for communicating with rabbitmq

        :returns: string transport URL
        """
        if self.hosts:
            hosts = self.hosts.split(',')
        else:
            hosts = [self.host]
        if hosts:
            transport_url_hosts = ','.join([
                "{}:{}@{}:{}".format(self.username,
                                     self.password,
                                     host_,
                                     self.port)
                for host_ in hosts])
            return "rabbit://{}/{}".format(transport_url_hosts, self.vhost)

    @property
    def port(self):
        """Return the port for commuicating with rabbitmq

        :returns: int port number
        """
        return self.ssl_port or self.DEFAULT_PORT


class ManilaRelationAdapters(
        charms_openstack.adapters.OpenStackAPIRelationAdapters):
    """
    Adapters collection to append specific adapters for Manila
    """

    relation_adapters = {
        'amqp': TransportURLAdapter,
        'shared_db': charms_openstack.adapters.DatabaseRelationAdapter,
        'cluster': charms_openstack.adapters.PeerHARelationAdapter,
        'coordinator_memcached': (
            charms_openstack.adapters.MemcacheRelationAdapter),
    }


###
# Implementation of the Manila Charm classes

class ManilaCharm(charms_openstack.charm.HAOpenStackCharm):
    """ManilaCharm provides the specialisation of the OpenStackCharm
    functionality to manage a manila unit.
    """

    release = 'mitaka'
    name = 'manila'
    group = 'manila'
    packages = PACKAGES
    api_ports = {
        'manila-api': {
            os_ip.PUBLIC: 8786,
            os_ip.ADMIN: 8786,
            os_ip.INTERNAL: 8786,
        },
    }
    service_type = 'manila'
    # manila needs a second service type as well - there is a custom connect
    # function to set both service types.
    service_type_v2 = 'manilav2'

    default_service = 'manila-api'

    # Note that the hsm interface is optional - defined in config.yaml
    required_relations = ['shared-db', 'amqp', 'identity-service']

    adapters_class = ManilaRelationAdapters

    # This is the command to sync the database
    sync_cmd = ['sudo', 'manila-manage', 'db', 'sync']

    # Package for release version detection
    release_pkg = 'manila-common'

    # Package codename map for manila-common
    package_codenames = {
        'manila-common': collections.OrderedDict([
            ('2', 'mitaka'),
            ('3', 'newton'),
            ('4', 'ocata'),
            ('5', 'pike'),
            ('6', 'queens'),
            ('7', 'rocky'),
            ('8', 'stein'),
            ('9', 'train'),
        ]),
    }

    @property
    def services(self):
        services = ['apache2',
                    'haproxy',
                    'manila-scheduler',
                    'manila-data']
        if not self.get_adapter('remote-manila-plugin.available'):
            services.append('manila-share')
        return services

    @property
    def restart_map(self):
        services = self.services
        return {
            MANILA_CONF: services,
            MANILA_API_PASTE_CONF: ['apache2'],
            MANILA_LOGGING_CONF: services,
            MANILA_WSGI_CONF: ['apache2'],
        }

    ha_resources = ['vips', 'haproxy', 'dnsha']

    # Custom charm configuration

    def install(self):
        """Called when the charm is being installed or upgraded.

        The available configuration options need to be check AFTER the charm is
        installed to check to see whether it is blocked or can go into service.
        """
        super().install()
        # this creates the /etc/nova directory for the
        # neutron-openvswitch plugin if needed.
        subprocess.check_call(["mkdir", "-p", "/etc/nova"])
        host.service_pause('manila-api')
        self.assess_status()

    def custom_assess_status_check(self):
        """Verify that the configuration provided is valid and thus the service
        is ready to go.  This will return blocked if the configuration is not
        valid for the service.

        :returns (status: string, message: string): the status, and message if
            there is a problem. Or (None, None) if there are no issues.
        """
        options = self.options  # tiny optimisation for less typing.
        backends = options.computed_share_backends
        if not backends:
            return 'blocked', 'No share backends configured'
        default_share_backend = options.default_share_backend
        if not default_share_backend:
            return 'blocked', "'default-share-backend' is not set"
        if default_share_backend not in backends:
            return ('blocked',
                    "'default-share-backend:{}' is not a configured backend"
                    .format(default_share_backend))
        return None, None

    def get_amqp_credentials(self):
        """Provide the default amqp username and vhost as a tuple.

        :returns (username, host): two strings to send to the amqp provider.
        """
        return (self.options.rabbit_user, self.options.rabbit_vhost)

    def get_database_setup(self):
        """Provide the default database credentials as a list of 3-tuples

        returns a structure of:
        [
            {'database': <database>,
             'username': <username>,
             'hostname': <hostname of this unit>
             'prefix': <the optional prefix for the database>, },
        ]

        :returns [{'database': ...}, ...]: credentials for multiple databases
        """
        return [
            dict(
                database=self.options.database,
                username=self.options.database_user, )
        ]

    def register_endpoints(self, keystone):
        """Custom function to register the TWO keystone endpoints that this
        charm requires.  'charm' and 'charmv2'.

        :param keystone: the keystone relation on which to setup the endpoints
        """
        # register the first endpoint
        self._custom_register_endpoints(keystone, 'v1',
                                        self.service_type,
                                        self.region,
                                        self.public_url,
                                        self.internal_url,
                                        self.admin_url)
        # register the second endpoint
        self._custom_register_endpoints(keystone, 'v2',
                                        self.service_type_v2,
                                        self.region,
                                        self.public_url_v2,
                                        self.internal_url_v2,
                                        self.admin_url_v2)

    @staticmethod
    def _custom_register_endpoints(keystone, prefix, service, region,
                                   public_url, internal_url, admin_url):
        """Custom function to enable registering of multiple endpoints.

        Keystone charm understands multiple endpoints if they are prefixed with
        a string_  as in 'v1_service' and 'v2_service', etc.  However, the
        keystone interface doesn't know how to do this.  Therefore, this
        function duplicates part of that functionality but enables the
        'multiple' endpoints to be set

        :param keystone: the relation that is keystone.
        :param prefix: the prefix to prepend to '_<var>'
        :param service: the service to set
        :param region: the OS region
        :param public_url: the public_url
        :param internal_url: the internal_url
        :prarm admin_url: the admin url.
        """
        relation_info = {
            '{}_service'.format(prefix): service,
            '{}_public_url'.format(prefix): public_url,
            '{}_internal_url'.format(prefix): internal_url,
            '{}_admin_url'.format(prefix): admin_url,
            '{}_region'.format(prefix): region,
        }
        keystone.set_local(**relation_info)
        keystone.set_remote(**relation_info)

    @property
    def public_url(self):
        return super().public_url + "/v1/%(tenant_id)s"

    @property
    def admin_url(self):
        return super().admin_url + "/v1/%(tenant_id)s"

    @property
    def internal_url(self):
        return super().internal_url + "/v1/%(tenant_id)s"

    @property
    def public_url_v2(self):
        return super().public_url + "/v2/%(tenant_id)s"

    @property
    def admin_url_v2(self):
        return super().admin_url + "/v2/%(tenant_id)s"

    @property
    def internal_url_v2(self):
        return super().internal_url + "/v2/%(tenant_id)s"

    @property
    def configured_backends(self):
        """Return a list of configured backends that come from the associated
        'manila-share.available' state..

        TODO: Note that the first backend that becomes 'available' will set
        this state.  It's not clear how multiple backends will interact yet!

        :returns: list of strings: backend sections that are configured.
        """
        adapter = self.adapter
        if adapter is None:
            return []
        # adapter.names is a property that provides a list of backend manila
        # plugin names for the sections
        return adapter.relation.names

    def config_lines_for(self, config_file):
        """Return the list of configuration lines for `config_file` as returned
        by manila-plugin backend charms.

        The configuration from the adapter looks like:

        {
            "<name1>": {
                "<config file path>": <string>,
                "<config file path 2>": <string>
            },
            "<name2>": {
                "<config file path>": <string>,
            },
        }

        :param config_file: string, filename for configuration lines
        :returns: list of strings: config lines for `config_file`
        """
        adapter = self.adapter
        if adapter is None:
            return []
        # get the configuration data for all plugins
        config_data = adapter.relation.get_configuration_data()
        # make the config_data <config_file>: {<name>: string} format
        inverted_config_data = {}
        for name, config_files in config_data.items():
            for file, data in config_files.items():
                if file not in inverted_config_data:
                    inverted_config_data[file] = {}
                inverted_config_data[file][name] = data
        # now see if it's the one we want
        if config_file not in inverted_config_data:
            return []
        config_lines = []
        for name, chunk in inverted_config_data[config_file].items():
            config_lines.append(chunk)
            config_lines.append('')
        return config_lines

    def config_files(self):
        """Return a set of all the config files that want to be written by the
        subordinate charms.

        :returns: [list of config files]
        """
        adapter = self.adapter
        if adapter is None:
            return []
        # get the configuration data for all plugins
        config_data = adapter.relation.get_configuration_data()

        config_files = set()
        for name, data in config_data.items():
            for config_file, chunks in data.items():
                config_files.add(config_file)
        return list(config_files)

    @property
    def adapter(self):
        return self.get_adapter('manila-plugin.available') or \
            self.get_adapter('remote-manila-plugin.available')

    def enable_webserver_site(self):
        """Enable Manila API apache2 site if rendered or installed"""
        if os.path.exists(MANILA_WSGI_CONF):
            check_enabled = subprocess.call(
                ['a2query', '-s', MANILA_WEBSERVER_SITE]
            )
            if check_enabled != 0:
                subprocess.check_call(['a2ensite',
                                       MANILA_WEBSERVER_SITE])
                host.service_reload('apache2',
                                    restart_on_failure=True)


class ManilaCharmRocky(ManilaCharm):

    release = 'rocky'

    packages = [
        'manila-api',
        'manila-data',
        'manila-scheduler',
        'manila-share',
        'python3-manila',
        'apache2',
        'libapache2-mod-wsgi-py3',
    ]

    purge_packages = [
        'python-manila',
        'python-memcache',
        'python-pymysql',
        'libapache2-mod-wsgi',
    ]

    python_version = 3
