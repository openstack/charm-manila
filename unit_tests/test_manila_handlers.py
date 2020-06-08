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

from unittest import mock

import reactive.manila_handlers as handlers

import charms_openstack.test_utils as test_utils


class TestRegisteredHooks(test_utils.TestRegisteredHooks):

    def test_hooks(self):
        defaults = [
            'charm.installed',
            'amqp.connected',
            'shared-db.connected',
            'certificates.available',
        ]
        hook_set = {
            'when': {
                'render_stuff': ('shared-db.available',
                                 'identity-service.available',
                                 'amqp.available', ),
                'register_endpoints': ('identity-service.connected', ),
                'share_to_manila_plugins_auth':
                    ('identity-service.connected', ),
                'maybe_do_syncdb': ('shared-db.available',
                                    'manila.config.rendered', ),
                'config_changed': ('shared-db.available',
                                   'identity-service.available',
                                   'amqp.available', ),
                'config_rendered': ('db.synced', 'manila.config.rendered',),
                'cluster_connected': ('ha.connected',),
                'configure_nrpe': ('config.rendered',)
            },
            'when_not': {
                'register_endpoints': ('identity-service.available', ),
                'maybe_do_syncdb': ('db.synced',),
                'config_rendered': ('config.rendered',)
            },
            'when_any': {
                'config_changed': ('config-changed',
                                   'manila-plugin.changed',
                                   'remote-manila-plugin.changed', ),
                'share_to_manila_plugins_auth': (
                    'manila-plugin.connected',
                    'remote-manila-plugin.connected', ),
                'configure_nrpe': (
                    'config.changed.nagios_context',
                    'config.changed.nagios_servicegroups',
                    'endpoint.nrpe-external-master.changed',
                    'nrpe-external-master.available', )
            },
            'when_none': {
                'configure_nrpe': ('charm.paused', 'is-update-status-hook', )
            }
        }
        # test that the hooks were registered via the
        # reactive.barbican_handlers
        self.registered_hooks_test_helper(handlers, hook_set, defaults)


class TestRenderStuff(test_utils.PatchHelper):

    def _patch_provide_charm_instance(self):
        manila_charm = mock.MagicMock()
        self.patch('charms_openstack.charm.provide_charm_instance',
                   name='provide_charm_instance',
                   new=mock.MagicMock())
        self.provide_charm_instance().__enter__.return_value = manila_charm
        self.provide_charm_instance().__exit__.return_value = None
        return manila_charm

    def test_register_endpoints(self):
        manila_charm = self._patch_provide_charm_instance()
        handlers.register_endpoints('keystone')
        manila_charm.register_endpoints.assert_called_once_with('keystone')
        manila_charm.assess_status.assert_called_once_with()

    def test_maybe_do_syncdb(self):
        manila_charm = self._patch_provide_charm_instance()
        handlers.maybe_do_syncdb('shared_db')
        manila_charm.db_sync.assert_called_once_with()

    def test_render_stuff(self):
        manila_charm = self._patch_provide_charm_instance()
        self.patch('charms.reactive.set_state', name='set_state')
        manila_charm.get_state.side_effect = [False, True]

        tls = mock.MagicMock()
        manila_plugin = mock.MagicMock()
        keystone = mock.MagicMock()
        flags_to_endpoints = {
            'certificates.available': tls,
            'identity-service.available': keystone,
            'manila-plugin.changed': manila_plugin,
            'remote-manila-plugin.changed': manila_plugin,
        }

        def fake_endpoint_from_flag(flag):
            return flags_to_endpoints[flag]

        self.patch('charms.reactive.relations.endpoint_from_flag',
                   name='endpoint_from_flag',
                   side_effect=fake_endpoint_from_flag)
        handlers.render_stuff('arg1', 'arg2')
        manila_charm.render_with_interfaces.assert_called_once_with(
            ('arg1', 'arg2', ))
        manila_charm.assess_status.assert_called_once_with()
        self.set_state.assert_called_once_with('manila.config.rendered')
        manila_plugin.clear_changed.assert_called_once_with()
        manila_charm.configure_tls.assert_called_once_with(
            certificates_interface=tls)
        manila_charm.register_endpoints.assert_called_once_with(keystone)

    def test_render_stuff_no_tls_change(self):
        manila_charm = self._patch_provide_charm_instance()
        self.patch('charms.reactive.set_state', name='set_state')
        manila_charm.get_state.side_effect = [True, True]

        tls = mock.MagicMock()
        manila_plugin = mock.MagicMock()
        keystone = mock.MagicMock()
        flags_to_endpoints = {
            'certificates.available': tls,
            'identity-service.available': keystone,
            'manila-plugin.changed': manila_plugin,
            'remote-manila-plugin.changed': manila_plugin,
        }

        def fake_endpoint_from_flag(flag):
            return flags_to_endpoints[flag]

        self.patch('charms.reactive.relations.endpoint_from_flag',
                   name='endpoint_from_flag',
                   side_effect=fake_endpoint_from_flag)
        handlers.render_stuff('arg1', 'arg2')
        manila_charm.render_with_interfaces.assert_called_once_with(
            ('arg1', 'arg2', ))
        manila_charm.assess_status.assert_called_once_with()
        self.set_state.assert_called_once_with('manila.config.rendered')
        manila_plugin.clear_changed.assert_called_once_with()
        manila_charm.configure_tls.assert_called_once_with(
            certificates_interface=tls)
        manila_charm.register_endpoints.assert_not_called()

    def test_config_changed(self):
        self.patch_object(handlers, 'render_stuff')
        handlers.config_changed('hello', 'there')
        self.render_stuff.assert_called_once_with('hello', 'there')
