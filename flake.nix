{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix, ... }:
    flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs { inherit system; };
      inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; })
        mkPoetryEnv mkPoetryApplication defaultPoetryOverrides;
      #poetryEnv = mkPoetryEnv {
      #  projectDir = ./.;
      #};
    in {
      packages = {
        ps2isopatcher = mkPoetryApplication {
          projectDir = self;
          overrides = defaultPoetryOverrides.extend
            (final: prev: {
              hatchling = prev.hatchling.overridePythonAttrs
              (
                old: {
                  buildInputs = (old.buildInputs or [ ]) ++ [ prev.pluggy ];
                }
              );
            });
        };
        default = self.packages.${system}.ps2isopatcher;
      };
      #devShells.default = pkgs.mkShell {
      #  buildInputs = [
      #    poetryEnv
      #  ];
      #};
      devShells.poetry = pkgs.mkShell {
        buildInputs = [
          # Required to make poetry shell work properly
          pkgs.bashInteractive
        ];
        packages = [
          pkgs.poetry
        ];
      };
    });
}