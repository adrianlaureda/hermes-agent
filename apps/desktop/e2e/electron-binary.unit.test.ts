import * as fs from 'node:fs'
import * as os from 'node:os'
import * as path from 'node:path'

import { afterEach, describe, expect, it } from 'vitest'

import { electronBinaryName, electronDistCandidates, pathLookupCommand, resolveElectronBinary } from './electron-binary'

const temporaryDirectories: string[] = []
const originalPath = process.env.PATH

afterEach(() => {
  process.env.PATH = originalPath

  for (const directory of temporaryDirectories.splice(0)) {
    fs.rmSync(directory, { recursive: true, force: true })
  }
})

function temporaryDirectory(): string {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-electron-binary-'))
  temporaryDirectories.push(directory)
  return directory
}

function fakeElectronPackage(root: string): string {
  const packageDirectory = path.join(root, 'node_modules', 'electron')
  const binary = path.join(packageDirectory, 'dist', electronBinaryName())

  fs.mkdirSync(path.dirname(binary), { recursive: true })
  fs.writeFileSync(
    path.join(packageDirectory, 'package.json'),
    JSON.stringify({ name: 'electron', version: '0.0.0', main: 'index.js' })
  )
  fs.writeFileSync(path.join(packageDirectory, 'index.js'), `module.exports = ${JSON.stringify(binary)}\n`)
  fs.writeFileSync(binary, '')

  return binary
}

function fakePathLookup(directory: string, output: string, status = 0): void {
  if (process.platform === 'win32') {
    throw new Error('Este fixture de PATH requiere un runner POSIX')
  }

  const script = `#!/bin/sh\nprintf '%s\\n' '${output.replaceAll("'", "'\\''")}'\nexit ${status}\n`
  const filePath = path.join(directory, pathLookupCommand())

  fs.writeFileSync(filePath, script)
  fs.chmodSync(filePath, 0o755)
}

// Se parametriza la plataforma para probar las reglas Windows también en CI Linux.
describe('electronBinaryName', () => {
  it('usa electron.exe en Windows', () => {
    expect(electronBinaryName('win32')).toBe('electron.exe')
  })

  it('usa electron en el resto de plataformas', () => {
    expect(electronBinaryName('linux')).toBe('electron')
    expect(electronBinaryName('darwin')).toBe('electron')
  })
})

describe('electronDistCandidates', () => {
  const desktop = path.join('repo', 'apps', 'desktop')
  const repo = 'repo'

  it('busca primero la instalación local del workspace', () => {
    expect(electronDistCandidates([desktop, repo], 'linux')).toEqual([
      path.join(desktop, 'node_modules', 'electron', 'dist', 'electron'),
      path.join(repo, 'node_modules', 'electron', 'dist', 'electron')
    ])
  })

  it('usa el nombre ejecutable de Windows en todas las rutas candidatas', () => {
    for (const candidate of electronDistCandidates([desktop, repo], 'win32')) {
      expect(path.basename(candidate)).toBe('electron.exe')
    }
  })
})

describe('pathLookupCommand', () => {
  it('usa where en Windows y which en el resto', () => {
    expect(pathLookupCommand('win32')).toBe('where')
    expect(pathLookupCommand('linux')).toBe('which')
    expect(pathLookupCommand('darwin')).toBe('which')
  })
})

describe('resolveElectronBinary', () => {
  it('prefiere el package export del workspace al package hoisted', () => {
    const root = temporaryDirectory()
    const desktop = path.join(root, 'apps', 'desktop')
    const repo = root
    const localBinary = fakeElectronPackage(desktop)
    const hoistedBinary = fakeElectronPackage(repo)

    expect(resolveElectronBinary([desktop, repo])).toBe(localBinary)
    expect(hoistedBinary).not.toBe(localBinary)
  })

  it('usa el package export hoisted cuando falta el local', () => {
    const root = temporaryDirectory()
    const desktop = path.join(root, 'apps', 'desktop')
    const hoistedBinary = fakeElectronPackage(root)

    expect(resolveElectronBinary([desktop, root])).toBe(hoistedBinary)
  })

  it.skipIf(process.platform === 'win32')('usa el binario encontrado en PATH si no hay packages instalados', () => {
    const root = temporaryDirectory()
    const pathDirectory = path.join(root, 'path-bin')
    const expected = path.join(root, 'path-electron', electronBinaryName())

    fs.mkdirSync(pathDirectory, { recursive: true })
    fakePathLookup(pathDirectory, expected)
    process.env.PATH = pathDirectory

    expect(resolveElectronBinary([path.join(root, 'empty')])).toBe(expected)
  })

  it.skipIf(process.platform === 'win32')('falla con un mensaje explícito cuando no encuentra Electron', () => {
    const root = temporaryDirectory()
    const pathDirectory = path.join(root, 'path-bin')

    fs.mkdirSync(pathDirectory, { recursive: true })
    fakePathLookup(pathDirectory, '', 1)
    process.env.PATH = pathDirectory

    expect(() => resolveElectronBinary([path.join(root, 'empty')])).toThrow(/Electron binary not found/)
  })
})
