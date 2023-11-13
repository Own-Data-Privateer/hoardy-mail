{ pkgs ? import <nixpkgs> {}
, lib ? pkgs.lib
, debug ? false
}:

with pkgs.python3Packages;

buildPythonApplication (rec {
  pname = "imaparms";
  version = "1.9";
  format = "pyproject";

  src = lib.cleanSourceWith {
    src = ./.;
    filter = name: type: let baseName = baseNameOf (toString name); in
      lib.cleanSourceFilter name type && ! (
        (baseName == "default.nix") ||
        (baseName == "dist") ||
        (baseName == "result") ||
        (baseName == "results") ||
        (baseName == "__pycache__")
      );
  };

  propagatedBuildInputs = [
    setuptools
  ];
} // lib.optionalAttrs debug {
  nativeBuildInputs = [
    mypy
  ];

  preBuild = "mypy";
})
