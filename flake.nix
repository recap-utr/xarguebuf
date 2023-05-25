{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-22.11";
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
          inherit (poetry2nix.legacyPackages.${system}) mkPoetryApplication mkPoetryEnv;
          poetryArgs = {
            projectDir = ./.;
            preferWheels = true;
            python = pkgs.python311;
          };
          venv = mkPoetryEnv poetryArgs;
          app = mkPoetryApplication poetryArgs;
        in
        {
          apps.copyDockerImage = {
            type = "app";
            program = builtins.toString (pkgs.writeShellScript "copyDockerImage" ''
              IFS=$'\n' # iterate over newlines
              set -x # echo on
              for DOCKER_TAG in $DOCKER_METADATA_OUTPUT_TAGS; do
                ${lib.getExe pkgs.skopeo} copy "docker-archive:${self'.packages.dockerImage}" "docker://$DOCKER_TAG"
              done
            '');
          };
          packages = {
            twitter2arguebuf = app;
            default = app;
            dockerImage = pkgs.dockerTools.buildImage {
              name = "twitter2arguebuf";
              config = {
                entrypoint = [ (lib.getExe app) ];
                cmd = [ "--help" ];
              };
            };
          };
          devShells.default = pkgs.mkShell {
            shellHook = ''
              ln -sfn ${venv} .venv
            '';
            packages = [ venv pkgs.poetry ];
          };
        };
    };
}
