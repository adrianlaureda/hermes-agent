#!/usr/bin/env bash
# run-tests.sh — ejecuta la suite SIN tocar el ~/.hermes real.
#
# Por que existe: el 2026-07-29 `pytest tests/cron` escribio 39 jobs reales en
# ~/.hermes/cron/ del perfil root ('w', 'c', 't', 's', 'claim job',
# 'paused job'). Quedaron habilitados y sin schedule valido, el scheduler los
# reintentaba en bucle y cada intento arrancaba un agente que moria con
# ImportError. Con kern.maxproc=6000 el Mac Mini acabo sin poder crear ni un
# shell: sshd autenticaba pero devolvia "exec request failed on channel 0".
# Hubo que reiniciarlo fisicamente.
#
# La causa es que cron/jobs.py fija CRON_DIR y JOBS_FILE AL IMPORTAR el modulo.
# Exportar HERMES_HOME desde dentro de un fixture llega tarde: hay que hacerlo
# antes de arrancar pytest. Eso es justo lo que hace este script.
#
# Uso:
#   ./run-tests.sh                    # toda la suite
#   ./run-tests.sh tests/cron         # una parte
#   ./run-tests.sh tests/cron -k foo  # con opciones de pytest
#
# Verificado: con HERMES_HOME aislado, la suite crea sus 6 jobs en el temporal
# y el perfil real se queda en 7.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$REPO/venv/bin/python"
[ -x "$PY" ] || PY=python3

HERMES_TEST_HOME="$(mktemp -d "${TMPDIR:-/tmp}/hermes-test-home.XXXXXX")"
mkdir -p "$HERMES_TEST_HOME/cron"

limpiar() {
    # Se borra solo lo que ha creado este script, dentro de su propio mktemp.
    [ -n "${HERMES_TEST_HOME:-}" ] && [ -d "$HERMES_TEST_HOME" ] && \
        find "$HERMES_TEST_HOME" -depth -delete 2>/dev/null || true
}
trap limpiar EXIT

echo "HERMES_HOME aislado en: $HERMES_TEST_HOME"

# Foto del perfil real para poder avisar si aun asi lo tocan.
REAL_JOBS="$HOME/.hermes/cron/jobs.json"
ANTES=""
[ -f "$REAL_JOBS" ] && ANTES="$(shasum -a 256 "$REAL_JOBS" | cut -d" " -f1)"

set +e
HERMES_HOME="$HERMES_TEST_HOME" "$PY" -m pytest "$@"
CODIGO=$?
set -e

if [ -n "$ANTES" ] && [ -f "$REAL_JOBS" ]; then
    DESPUES="$(shasum -a 256 "$REAL_JOBS" | cut -d" " -f1)"
    if [ "$ANTES" != "$DESPUES" ]; then
        echo
        echo "================================================================"
        echo "  AVISO: los tests han modificado $REAL_JOBS"
        echo "  Revisalo: puede haber quedado un job de test habilitado."
        echo "================================================================"
    fi
fi

exit $CODIGO
