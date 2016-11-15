# Manila Source Charm

THIS CHARM IS FOR EXPERIMENTAL USE AT PRESENT.  This is a pre-release charm for
the Manila service to enable testing and to inform further development. It
shouldn't be used in production environments yet.  Note that the OpenStack
manila service *is* production ready (according to their website).

This repository is for the reactive, layered,
[Manila](https://wiki.openstack.org/wiki/Manila) _source_ charm.

Please see the src/README.md for details on the built Manila charm and how to
use it.

## Building the charm

To build the charm run the following command in the root of the repository:

```bash
$ tox -e build
```

The resultant built charm will be in the builds directory.

## Development/Hacking of the charm

Please see HACKING.md in this directory.
