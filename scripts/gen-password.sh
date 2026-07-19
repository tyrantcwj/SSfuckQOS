#!/bin/sh
# Generate a strong password for SS_PASSWORD
openssl rand -base64 24 2>/dev/null || head -c 32 /dev/urandom | base64
