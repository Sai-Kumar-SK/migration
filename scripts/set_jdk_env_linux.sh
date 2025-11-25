#!/usr/bin/env bash
set -euo pipefail

# Usage: ./set_jdk_env_linux.sh /usr/lib/jvm/java-8 /usr/lib/jvm/java-11 /usr/lib/jvm/java-17 /usr/lib/jvm/java-21
JAVA8=${1:-/usr/lib/jvm/java-8}
JAVA11=${2:-/usr/lib/jvm/java-11}
JAVA17=${3:-/usr/lib/jvm/java-17}
JAVA21=${4:-/usr/lib/jvm/java-21}

echo "Exporting JAVA*_HOME in your shell profile (~/.bashrc)"
{
  echo "export JAVA8_HOME=\"$JAVA8\""
  echo "export JAVA11_HOME=\"$JAVA11\""
  echo "export JAVA17_HOME=\"$JAVA17\""
  echo "export JAVA21_HOME=\"$JAVA21\""
} >> "$HOME/.bashrc"

echo "Done. Run: source ~/.bashrc"