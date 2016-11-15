# Overview

Pre-release charm for testing:

This charm provides the Manila shared file service for an OpenStack Cloud.  It
installs a single instance that, on its own, can't be used.

In order to use the manila charm, a suitable backend charm is needed to
configure a share backend.  At the time of writing (Dec 2016) the only backend
charm available for testing is the 'generic backend' charm called
'manila-generic'.  This is used to configure a generic fileshare backend that
can implement an NFS server that then uses a cinder backend block storage
service to provide the share instances.

Without a backend subordinate charm related to the manila-charm there will be
no manila backends configured; the manila charm will be stuck in the blocked
state.


## Manila share backends are configured using subordinate charms

It's necessary to have the ability to configure a share backend independently
of the main charm.  This means that plugin charms will be used to configure
each backend.  Multiple backend charms can be related to the manila charm to
allow a manaila (juju) application to support multiple share backends.

Essentially, a plugin needs to be able to configure:

 - it's section in the manila.conf along with any network plugin's that it
   needs (assuming that it's a share that manages it's own share-instance).
 - ensure that the relevant services are restarted.

This pre-release of manila provides (in the charm store):

 - charm-manila: the main charm,
 - interface-manila-plugin : the interface for plugging in the generic
   backend (and other interfaces),
 - charm-manila-generic: the plugin for configuring the generic backend.

The backend provides a piece of the manila.conf configuration file with
the sections necessary to configure the backend.  This is mostly for the share,
rather than the api level.

# Usage

Manila (plus manila-generic) relies on services from the mysql/percona,
rabbitmq-server, keystone charms, and a storage backend charm.  The following
yaml file will create a small, unconfigured, OpenStack system with the
necessary components to start testing with Manila.  Note that these target the
'next' OpenStack charms which are essentially 'edge' charms.

```yaml

# vim: set ts=2 et:
# Juju 2.0 deploy bundle for development ('next') charms
# UOSCI relies on this for OS-on-OS deployment testing
series: xenial
automatically-retry-hooks: False
services:
  mysql:
    charm: cs:~openstack-charmers/xenial/percona-cluster
    num_units: 1
    constraints: mem=1G
    options:
      dataset-size: 50%
      root-password: mysql
  rabbitmq-server:
    charm: cs:~openstack-charmers/xenial/rabbitmq-server
    num_units: 1
    constraints: mem=1G
  keystone:
    charm: cs:~openstack-charmers/xenial/keystone
    num_units: 1
    constraints: mem=1G
    options:
      admin-password: openstack
      admin-token: ubuntutesting
      preferred-api-version: "2"
  glance:
    charm: cs:~openstack-charmers/xenial/glance
    num_units: 1
    constraints: mem=1G
  nova-cloud-controller:
    charm: cs:~openstack-charmers/xenial/nova-cloud-controller
    num_units: 1
    constraints: mem=1G
    options:
      network-manager: Neutron
  nova-compute:
    charm: cs:~openstack-charmers/xenial/nova-compute
    num_units: 1
    constraints: mem=4G
  neutron-gateway:
    charm: cs:~openstack-charmers/xenial/neutron-gateway
    num_units: 1
    constraints: mem=1G
    options:
      bridge-mappings: physnet1:br-ex
      instance-mtu: 1300
  neutron-api:
    charm: cs:~openstack-charmers/xenial/neutron-api
    num_units: 1
    constraints: mem=1G
    options:
      neutron-security-groups: True
      flat-network-providers: physnet1
  neutron-openvswitch:
    charm: cs:~openstack-charmers/xenial/neutron-openvswitch
  cinder:
    charm: cs:~openstack-charmers/xenial/cinder
    num_units: 1
    constraints: mem=1G
    options:
      block-device: vdb
      glance-api-version: 2
      overwrite: 'true'
      ephemeral-unmount: /mnt
  manila:
    charm: cs:~openstack-charmers/xenial/manila
    num_units: 1
    options:
      debug: True
  manila-generic:
      charm: cs:~openstack-charmers/xenial/manila-generic
    options:
      debug: True
relations:
  - [ keystone, mysql ]
  - [ manila, mysql ]
  - [ manila, rabbitmq-server ]
  - [ manila, keystone ]
  - [ manila, manila-generic ]
  - [ glance, keystone]
  - [ glance, mysql ]
  - [ glance, "cinder:image-service" ]
  - [ nova-compute, "rabbitmq-server:amqp" ]
  - [ nova-compute, glance ]
  - [ nova-cloud-controller, rabbitmq-server ]
  - [ nova-cloud-controller, mysql ]
  - [ nova-cloud-controller, keystone ]
  - [ nova-cloud-controller, glance ]
  - [ nova-cloud-controller, nova-compute ]
  - [ cinder, keystone ]
  - [ cinder, mysql ]
  - [ cinder, rabbitmq-server ]
  - [ cinder, nova-cloud-controller ]
  - [ "neutron-gateway:amqp", "rabbitmq-server:amqp" ]
  - [ neutron-gateway, nova-cloud-controller ]
  - [ neutron-api, mysql ]
  - [ neutron-api, rabbitmq-server ]
  - [ neutron-api, nova-cloud-controller ]
  - [ neutron-api, neutron-openvswitch ]
  - [ neutron-api, keystone ]
  - [ neutron-api, neutron-gateway ]
  - [ neutron-openvswitch, nova-compute ]
  - [ neutron-openvswitch, rabbitmq-server ]
  - [ neutron-openvswitch, manila ]
```

and then (with juju 2.x):

```bash
    juju deploy manila.yaml
```

Note that this OpenStack system will need to be configured (in terms of
networking, images, etc.) before testing can commence.

# Bugs

Please report bugs on [Launchpad](https://bugs.launchpad.net/charm-manila/+filebug).

For general questions please refer to the OpenStack [Charm Guide](https://github.com/openstack/charm-guide).
