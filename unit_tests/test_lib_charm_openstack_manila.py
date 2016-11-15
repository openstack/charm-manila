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

import charm.openstack.manila as manila

import charms_openstack.test_utils as test_utils


class Helper(test_utils.PatchHelper):

    def setUp(self):
        super().setUp()
        self.patch_release(manila.ManilaCharm.release)


class TestManilaCharmUtilities(Helper):

    def test_strip_join(self):
        tests1 = (
            ("this is the one", "this is the one"),
            ("this, is, the one", "this is the one"),
            ("this     is,   the  one", "this is the one"))
        for (t, r) in tests1:
            self.assertEqual(r, manila.strip_join(t))
        tests2 = (
            ("this is the one", "this, is, the, one"),
            ("this, is, the one", "this, is, the, one"),
            ("this     is,   the  one", "this, is, the, one"))
        for (t, r) in tests2:
            self.assertEqual(r, manila.strip_join(t, divider=", "))


class TestManilaCharmConfigProperties(Helper):

    def test_computed_share_backends(self):
        config = mock.MagicMock()
        config.charm_instance.configured_backends = ["a", "c", "b"]
        self.assertEqual(manila.computed_share_backends(config), "a c b")

    def test_computed_share_protocols(self):
        config = mock.MagicMock()
        config.share_protocols = "a c b"
        self.assertEqual(manila.computed_share_protocols(config), "A,C,B")

    def test_computed_backend_lines_manila_conf(self):
        config = mock.MagicMock()
        config.share_protocols = "a c b"
        config.charm_instance.config_lines_for.return_value = "Test Value"
        self.assertEqual(manila.computed_backend_lines_manila_conf(config),
                         "Test Value")
        config.charm_instance.config_lines_for.assert_called_once_with(
            manila.MANILA_CONF)

    def test_computed_debug_level(self):
        config = mock.MagicMock()
        config.debug = False
        config.verbose = False
        self.assertEqual(manila.computed_debug_level(config), "NONE")
        config.verbose = True
        self.assertEqual(manila.computed_debug_level(config), "NONE")
        config.debug = True
        config.verbose = False
        self.assertEqual(manila.computed_debug_level(config), "WARNING")
        config.verbose = True
        self.assertEqual(manila.computed_debug_level(config), "DEBUG")


class TestManilaCharm(Helper):

    def _patch_config_and_charm(self, config):
        self.patch_object(manila.hookenv, 'config')

        def cf(key=None):
            if key is not None:
                return config[key]
            return config

        self.config.side_effect = cf
        c = manila.ManilaCharm()
        return c

    def test_install(self):
        self.patch("charms_openstack.charm.OpenStackCharm.install",
                   name="install")
        self.patch("subprocess.check_call", name="check_call")
        self.patch("charms_openstack.charm.OpenStackCharm.assess_status",
                   name="assess_status")
        c = manila.ManilaCharm()
        c.install()
        self.install.assert_called_once_with()
        self.check_call.assert_called_once_with(["mkdir", "-p", "/etc/nova"])
        self.assess_status.assert_called_once_with()

    def _patch_get_adapter(self, c):
        self.patch_object(c, 'get_adapter')

        def _helper(x):
            self.var = x
            return self.out

        self.get_adapter.side_effect = _helper

    def test_custom_assess_status_check1(self):
        config = {
            'default-share-backend': '',
        }
        c = self._patch_config_and_charm(config)
        self._patch_get_adapter(c)
        self.out = None

        self.assertEqual(c.configured_backends, [])
        self.assertEqual(c.custom_assess_status_check(),
                         ('blocked', 'No share backends configured'))
        self.out = mock.Mock()
        self.out.relation.names = ['name1']
        self.assertEqual(c.custom_assess_status_check(),
                         ('blocked', "'default-share-backend' is not set"))
        self.assertEqual(self.var, 'manila-plugin.available')

    def test_custom_assess_status_check2(self):
        config = {
            'default-share-backend': 'name2',
        }
        c = self._patch_config_and_charm(config)
        self._patch_get_adapter(c)
        self.out = mock.Mock()
        self.out.relation.names = ['name1']
        self.assertEqual(
            c.custom_assess_status_check(),
            ('blocked',
             "'default-share-backend:name2' is not a configured backend"))
        self.out.relation.names = ['name1', 'name2']
        self.assertEqual(c.custom_assess_status_check(), (None, None))

    def test_get_amqp_credentials(self):
        config = {
            'rabbit-user': 'rabbit1',
            'rabbit-vhost': 'password'
        }
        c = self._patch_config_and_charm(config)
        self.assertEqual(c.get_amqp_credentials(), ('rabbit1', 'password'))

    def test_get_database_setup(self):
        config = {
            'database': 'db1',
            'database-user': 'user1'
        }
        c = self._patch_config_and_charm(config)
        self.patch_object(manila.hookenv, 'unit_private_ip')
        self.unit_private_ip.return_value = 'ip1'
        self.assertEqual(
            c.get_database_setup(),
            [dict(database='db1', username='user1', hostname='ip1')])

    def test_register_endpoints(self):
        # note that this also tests _custom_register_endpoints() indirectly,
        # which means it doesn't require a separate test.
        keystone = mock.MagicMock()
        config = {
            'region': 'the_region',
        }
        c = self._patch_config_and_charm(config)
        self.patch_object(manila.ManilaCharm,
                          'public_url', new_callable=mock.PropertyMock)
        self.patch_object(manila.ManilaCharm,
                          'internal_url', new_callable=mock.PropertyMock)
        self.patch_object(manila.ManilaCharm,
                          'admin_url', new_callable=mock.PropertyMock)
        self.patch_object(manila.ManilaCharm,
                          'public_url_v2', new_callable=mock.PropertyMock)
        self.patch_object(manila.ManilaCharm,
                          'internal_url_v2', new_callable=mock.PropertyMock)
        self.patch_object(manila.ManilaCharm,
                          'admin_url_v2', new_callable=mock.PropertyMock)
        self.public_url.return_value = 'p1'
        self.internal_url.return_value = 'i1'
        self.admin_url.return_value = 'a1'
        self.public_url_v2.return_value = 'p2'
        self.internal_url_v2.return_value = 'i2'
        self.admin_url_v2.return_value = 'a2'
        c.register_endpoints(keystone)
        v1 = mock.call(v1_admin_url='a1',
                       v1_internal_url='i1',
                       v1_public_url='p1',
                       v1_region='the_region',
                       v1_service='manila')
        v2 = mock.call(v2_admin_url='a2',
                       v2_internal_url='i2',
                       v2_public_url='p2',
                       v2_region='the_region',
                       v2_service='manilav2')
        calls = [v1, v2]
        keystone.set_local.assert_has_calls(calls)
        keystone.set_remote.assert_has_calls(calls)

    def test_url_endpoints_creation(self):
        # Tests that the endpoint functions call through to the baseclass
        self.patch_object(manila.charms_openstack.charm.OpenStackCharm,
                          'public_url', new_callable=mock.PropertyMock)
        self.patch_object(manila.charms_openstack.charm.OpenStackCharm,
                          'internal_url', new_callable=mock.PropertyMock)
        self.patch_object(manila.charms_openstack.charm.OpenStackCharm,
                          'admin_url', new_callable=mock.PropertyMock)
        self.public_url.return_value = 'p1'
        self.internal_url.return_value = 'i1'
        self.admin_url.return_value = 'a1'
        c = self._patch_config_and_charm({})
        self.assertEqual(c.public_url, 'p1/v1/%(tenant_id)s')
        self.assertEqual(c.internal_url, 'i1/v1/%(tenant_id)s')
        self.assertEqual(c.admin_url, 'a1/v1/%(tenant_id)s')
        self.assertEqual(c.public_url_v2, 'p1/v2/%(tenant_id)s')
        self.assertEqual(c.internal_url_v2, 'i1/v2/%(tenant_id)s')
        self.assertEqual(c.admin_url_v2, 'a1/v2/%(tenant_id)s')

    def test_configured_backends(self):
        c = self._patch_config_and_charm({})
        self._patch_get_adapter(c)
        self.out = None
        self.assertEqual(c.configured_backends, [])
        self.assertEqual(self.var, 'manila-plugin.available')
        self.out = mock.Mock()
        self.out.relation.names = ['a', 'b']
        self.assertEqual(c.configured_backends, ['a', 'b'])

    def test_config_lines_for(self):
        c = self._patch_config_and_charm({})
        self._patch_get_adapter(c)
        self.out = None
        self.assertEqual(c.config_lines_for('conf'), [])
        self.assertEqual(self.var, 'manila-plugin.available')
        self.out = mock.Mock()
        self.out.relation.get_configuration_data.return_value = {}
        self.assertEqual(c.config_lines_for('conf'), [])
        config = {
            'conf': {
                'complete': True,
                '[section1]': (
                    'line1', 'line2'),
                '[section2]': (
                    'line3', ),
            },
            'conf2': {
                'complete': True,
                '[section3]': (
                    'line4', 'line5'),
            },
            'conf3': {
                'complete': False,
                '[section4]': (
                    'line6', 'line7'),
            }
        }
        self.out.relation.get_configuration_data.return_value = config
        self.assertEqual(c.config_lines_for('conf'), [
            '[section1]',
            'line1',
            'line2',
            '',
            '[section2]',
            'line3',
            ''])
        self.assertEqual(c.config_lines_for('conf2'), [
            '[section3]',
            'line4',
            'line5',
            ''])
        self.assertEqual(c.config_lines_for('conf3'), [])
