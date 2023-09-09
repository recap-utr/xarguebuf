{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    systems.url = "github:nix-systems/default";
  };
  outputs = inputs @ {
    nixpkgs,
    flake-parts,
    systems,
    ...
  }:
    flake-parts.lib.mkFlake {inherit inputs;} {
      systems = import systems;
      perSystem = {
        pkgs,
        system,
        lib,
        self',
        ...
      }: let
        python = pkgs.python310;
        poetry = pkgs.poetry;
        pkgName = "xarguebuf";
      in {
        packages = {
          default = pkgs.poetry2nix.mkPoetryApplication {
            inherit python;
            projectDir = ./.;
            preferWheels = true;
          };
          ${pkgName} = self'.packages.default;
          dockerImage = pkgs.dockerTools.buildLayeredImage {
            name = pkgName;
            tag = "latest";
            created = "now";
            config = {
              entrypoint = [(lib.getExe self'.packages.default)];
              cmd = ["--help"];
            };
          };
        };
        devShells.default = pkgs.mkShell {
          packages = [python poetry];
          buildInputs = with pkgs; [graphviz];
          POETRY_VIRTUALENVS_IN_PROJECT = true;
          shellHook = ''
            ${lib.getExe poetry} env use ${lib.getExe python}
            ${lib.getExe poetry} install --no-root --all-extras
            export BEARER_TOKEN=$(cat bearer-token.txt)
          '';
        };
      };
    };
}
