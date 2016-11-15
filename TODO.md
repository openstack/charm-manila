TODO
====

 * Add roles to the manila charm: api, scheduler, data, process, (all)
 * Ensure that HA is supported properly on the charm (and tested).
 * Pause/Resume - implement the pause/resume actions that other charms support.

## Add roles:

It's necessary for the manila charm to be able to install itself as one of a
number of roles:

 1. The manila-api: this provides the API to the rest of OpenStack.  Until this
    is HA aware, only ONE manila-api can be provisioned because it registers
    itself with the keystone identity-service.
 2. The manila-scheduler: Responsible for scheduling/routing requests to the
    appropriate manila-share service. It does that by picking one back-end
    while filtering all except one back-end.
 3. The manila-share process: Responsible for managing Shared File Service
    devices, specifically the back-end devices.
 4. The manila-data process: This is responsible, in the manila system, for
    data operations such as copying, migration, backups, etc.  It's not clear
    how far progressed that this service is.

Currently, the manila charm installs exactly one unit with all of the shared
services on the same unit.  This is fine for testing, but won't be particularly
suited for a production environment.

So, it is proposed to enable configuration of the charm to enable it to install
any/all of the roles.  This will then allow two manila (juju) applications to
be installed, such that (say) manila-api and manila-scheduler roles can be
configured as one (juju) application, and the manila-share as a seperate
application.  Manila allows for serveral, different, manila-share instances to
be deployed, which would mean a single manila-api/scheduler (juju) application
and several (juju) applications, one each for each different manila-share
instance in the OpenStack cloud.

## Support HA Mode

The charm has been implemented using the `HAOpenStackCharm` class, which means
that the plumbing is available to support multiple juju units, each with a
manila instance, with the API endpoints provided via an vip.  However, this has
not been tested, and before it can be declared 'production ready', this HA
modes need to be tested alongside the 'roles' discussed above.

## Pause/Resume

The charm does not implement the Pause/Resume actions that the other OpenStack
charms support.  This needs to be implemented if the charm will be a
well-behaved citizen like the other charms.
