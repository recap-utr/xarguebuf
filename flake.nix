{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.05";
    flake-parts.url = "github:hercules-ci/flake-parts";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };
  outputs = inputs@{ nixpkgs, flake-parts, poetry2nix, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = nixpkgs.lib.systems.flakeExposed;
      perSystem = { pkgs, system, lib, self', ... }:
        let
          python = pkgs.python311;
          poetry = pkgs.poetry;
        in
        {
          apps.copyDockerImage = {
            type = "app";
            program = builtins.toString (pkgs.writeShellScript "copyDockerImage" ''
              IFS=$'\n' # iterate over newlines
              set -x # echo on
              for DOCKER_TAG in $DOCKER_METADATA_OUTPUT_TAGS; do
                ${lib.getExe pkgs.skopeo} --insecure-policy copy "docker-archive:${self'.packages.dockerImage}" "docker://$DOCKER_TAG"
              done
            '');
          };
          packages =
            let
              inherit (poetry2nix.legacyPackages.${system}) mkPoetryApplication overrides;
              app = mkPoetryApplication {
                inherit python;
                projectDir = ./.;
                preferWheels = true;
                # overrides = overrides.withDefaults (self: super: {
                #   twarc = super.twarc.overridePythonAttrs (old: {
                #     propagatedBuildInputs = (old.propagatedBuildInputs or [ ]) ++ [ super.setuptools ];
                #   });
                #   click-config-file = super.click-config-file.overridePythonAttrs (old: {
                #     propagatedBuildInputs = (old.propagatedBuildInputs or [ ]) ++ [ super.setuptools ];
                #   });
                #   rich-click = super.rich-click.overridePythonAttrs (old: {
                #     propagatedBuildInputs = (old.propagatedBuildInputs or [ ]) ++ [ super.setuptools ];
                #   });
                #   typed-settings = super.typed-settings.overridePythonAttrs (old: {
                #     propagatedBuildInputs = (old.propagatedBuildInputs or [ ]) ++ [ super.hatchling ];
                #   });
                #   grpc-stubs = super.grpc-stubs.overridePythonAttrs (old: {
                #     propagatedBuildInputs = (old.propagatedBuildInputs or [ ]) ++ [ super.setuptools ];
                #   });
                #   arg-services = super.arg-services.overridePythonAttrs (old: {
                #     propagatedBuildInputs = (old.propagatedBuildInputs or [ ]) ++ [ super.poetry ];
                #   });
                # });
              };
            in
            {
              twitter2arguebuf = app;
              default = app;
              dockerImage = pkgs.dockerTools.buildImage {
                name = "twitter2arguebuf";
                tag = "latest";
                created = "now";
                config = {
                  entrypoint = [ (lib.getExe app) ];
                  cmd = [ "--help" ];
                };
              };
            };
          devShells.default = pkgs.mkShell {
            packages = [ python poetry pkgs.graphviz ];
            shellHook = ''
              export POETRY_VIRTUALENVS_IN_PROJECT=1
              ${lib.getExe poetry} env use ${lib.getExe python}
              ${lib.getExe poetry} install --no-root
            '';
          };
        };
    };
}
