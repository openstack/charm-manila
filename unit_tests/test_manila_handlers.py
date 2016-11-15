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

from __future__ import absolute_import
from __future__ import print_function

import mock

import reactive.manila_handlers as handlers

import charms_openstack.test_utils as test_utils


class TestRegisteredHooks(test_utils.TestRegisteredHooks):

    def test_hooks(self):
        defaults = [
            'charm.installed',
            'amqp.connected',
            'shared-db.connected',
            'identity-service.available',  # enables SSL support
        ]
        hook_set = {
            'when': {
                'render_stuff': ('shared-db.available',
                                 'identity-service.available',
                                 'amqp.available', ),
                'register_endpoints': ('identity-service.connected', ),
                'share_to_manila_plugins_auth': ('identity-service.connected',
                                                 'manila-plugin.connected', ),
                'maybe_do_syncdb': ('shared-db.available',
                                    'manila.config.rendered', ),
                'config_changed': ('config.changed',
                                   'shared-db.available',
                                   'identity-service.available',
                                   'amqp.available', )
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

        handlers.render_stuff('arg1', 'arg2')
        manila_charm.render_with_interfaces.assert_called_once_with(
            ('arg1', 'arg2', ))
        manila_charm.assess_status.assert_called_once_with()
        self.set_state.assert_called_once_with('manila.config.rendered')

    def test_config_changed(self):
        self.patch_object(handlers, 'render_stuff')
        handlers.config_changed('hello', 'there')
        self.render_stuff.assert_called_once_with('hello', 'there')
