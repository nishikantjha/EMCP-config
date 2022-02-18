#!/usr/bin/env bash

# This script uses arg $1 (name of *.jsonnet file to use) to generate the manifests/*.yaml files.

set -e
set -x
# only exit with zero if all commands of the pipeline exit successfully
set -o pipefail

# Make sure to use project tooling
PATH="$(pwd)/tmp/bin:${PATH}"

# set path to which to write the manifests files
MANIFESTS_PATH="../ansible/roles/k8s_setup_monitoring/files/manifests"

# Make sure to start with a clean 'manifests' dir

if [ -d $MANIFESTS_PATH ]; then

  rm -rf $MANIFESTS_PATH
  mkdir -p "$MANIFESTS_PATH/setup"

  # Calling gojsontoyaml is optional, but we would like to generate yaml, not json
  jsonnet -J vendor -m $MANIFESTS_PATH "${1-example.jsonnet}" | xargs -I{} sh -c 'cat {} | gojsontoyaml > {}.yaml' -- {}

  # Make sure to remove json files
  find $MANIFESTS_PATH -type f ! -name '*.yaml' -delete
  rm -f kustomization

  # correct generated files
  find $MANIFESTS_PATH -name *CustomResourceDefinition.yaml -type f -print0 | xargs -0 sed -i "s/- \(=~*\)\$/- '\1'/g"
else
  echo "$MANIFESTS_PATH does not exist. Please make sure it is present."
fi
