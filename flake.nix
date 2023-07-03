{
  description = "intake feed sources";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/23.05";

  outputs = { self, nixpkgs }:
  let
    # Systems to build packages for.
    supportedSystems = [
      "x86_64-linux"
      "aarch64-linux"
    ];

    # Helper to create an attrset by applying a function to each system.
    forAllSystems = func: nixpkgs.lib.genAttrs supportedSystems func;
  in {
    # Build the package for each system by applying the default overlay to
    # the system and using the package it adds.
    packages = forAllSystems (system:
    {
      default = (import nixpkgs {
        inherit system;
        overlays = [ self.overlays.default ];
      }).mloader;
    });

    # Provide a default app that runs mloader.
    apps = forAllSystems (system: {
      default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/mloader";
      };
    });

    # Provide a default overlay that adds mloader to the package set.
    overlays.default = final: prev: let
      # with protobuf 3.21 the python package version is 4.21, so the last
      # version that satisfies the ~=3.6 constraint is 3.20
      py_protobuf_3_20 = final.python3Packages.protobuf.override {
        protobuf = final.protobuf3_20;
      };
    in {
      mloader = final.python3Packages.buildPythonPackage {
        name = "mloader";
        src = builtins.path { name = "mloader"; path = ./.; };
        format = "setuptools";
        propagatedBuildInputs = with final.python3Packages; [
          click
          py_protobuf_3_20
          requests
        ];
      };
    };

    # Provide a nixos module that applies the default overlay.
    nixosModules.default = {
      nixpkgs.overlays = [ self.overlays.default ];
    };
  };
}

