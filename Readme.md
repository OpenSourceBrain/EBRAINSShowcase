# EBRAINS Showcase

Scripts testing out the integration between EBRAINS and Open Source Brain v2.

## Unsupported locations

To see the list of models whose files reside on unsupported platforms, run this command in the main directory:

```
    $ grep '"repository":' scripts/ebrains-models.json | grep -v "github" | grep -v "object.cscs" | grep -v "modeldb" | grep -v "data-proxy" | grep -v "yale"
```
