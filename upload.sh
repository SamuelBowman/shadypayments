#!/usr/bin/env bash

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: $0 tcl_file serial_device"
    exit 1
fi

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
TCLOAD_DIR="${SCRIPT_DIR}/TCLOAD"

if [ ! -f "${TCLOAD_DIR}/$1" ]; then
    echo "Error: ${TCLOAD_DIR}/$1 does not exist"
    exit 1
fi

if [ ! -c "/dev/$2" ]; then
    echo "Error: /dev/$2 does not exist"
    exit 1
fi

echo "Press FUNC + # to receive"

dosbox \
    --set "serial1=direct realport:$2" \
    -c "mount c ${TCLOAD_DIR}" \
    -c "c:" \
    -c "TCLOAD $1 -t" \
    --exit \
    2> /dev/null
