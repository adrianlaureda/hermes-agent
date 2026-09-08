/**
 * Resuelve el binario Electron usado por los fixtures E2E.
 *
 * Portado de NousResearch/hermes-agent#99671. La resolución vive en este
 * módulo para poder probar las reglas de plataforma sin arrancar Playwright.
 */

import { spawnSync } from 'node:child_process'
import * as fs from 'node:fs'
import { createRequire } from 'node:module'
import * as path from 'node:path'

/** Nombre del ejecutable distribuido por Electron según la plataforma. */
export function electronBinaryName(platform: NodeJS.Platform = process.platform): string {
  return platform === 'win32' ? 'electron.exe' : 'electron'
}

/**
 * Rutas posibles de una instalación npm, en el orden de preferencia.
 * La instalación del workspace debe ganar a la copia hoisted del repositorio.
 */
export function electronDistCandidates(roots: string[], platform: NodeJS.Platform = process.platform): string[] {
  return roots.map(root => path.join(root, 'node_modules', 'electron', 'dist', electronBinaryName(platform)))
}

/** Comando de búsqueda del PATH en cada plataforma. */
export function pathLookupCommand(platform: NodeJS.Platform = process.platform): string {
  return platform === 'win32' ? 'where' : 'which'
}

/**
 * Pregunta al paquete Electron por su propio ejecutable.
 * `from` es la raíz de un workspace desde la que debe resolverse el paquete.
 */
export function electronPackagePath(from: string): string | null {
  try {
    const resolved = createRequire(path.join(from, 'package.json'))('electron') as unknown

    return typeof resolved === 'string' && resolved ? resolved : null
  } catch {
    return null
  }
}

/** Resuelve el ejecutable o informa de las rutas que se han inspeccionado. */
export function resolveElectronBinary(roots: string[]): string {
  for (const root of roots) {
    const declared = electronPackagePath(root)

    if (declared && fs.existsSync(declared)) {
      return declared
    }
  }

  for (const candidate of electronDistCandidates(roots)) {
    if (fs.existsSync(candidate)) {
      return candidate
    }
  }

  // Nix devshells pueden exponer Electron en PATH sin copia en node_modules.
  const lookup = spawnSync(pathLookupCommand(), ['electron'], { encoding: 'utf8' })

  if (lookup.status === 0 && lookup.stdout.trim()) {
    // `where` puede devolver varias coincidencias; la primera es la preferida.
    const first = lookup.stdout.trim().split(/\r?\n/)[0].trim()

    if (first) {
      return first
    }
  }

  throw new Error(
    `Electron binary not found. Searched ${electronDistCandidates(roots).join(', ')} and PATH. ` +
      'Run "npm install" from the repo root to install devDependencies.'
  )
}
