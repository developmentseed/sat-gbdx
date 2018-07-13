#!/usr/bin/env bash
for d in /tmp/* ; do
    if [[ -d $d ]]; then
         mv $d/*.tif tmp/
    fi
done