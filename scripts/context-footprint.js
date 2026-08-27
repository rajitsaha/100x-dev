#!/usr/bin/env node
'use strict'

const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const MODULES = path.join(REPO, 'adapters', 'lib', 'modules.py')
const BUDGETS = JSON.parse(fs.readFileSync(path.join(REPO, 'config', 'context-budgets.json'), 'utf8'))
const TOOLS = ['claude', 'cursor', 'codex', 'pi']
const GENERIC_DESCRIPTION = 'Load any routed 100xprism workflow by slug without indexing every workflow.'
const RESOLVER_DESCRIPTION = 'Catalog of specialist 100xprism workflows kept out of the always-on index — marketing, SEO, CRO, copywriting, growth, pricing, sales, design, accessibility, motion, and data-visualization playbooks. Read this file\'s table to find the right one, then read that module\'s SKILL.md path before starting the work.'

function shortDescription(value) {
  let text = String(value || '').split('. ')[0]
  if (text.length > 140) text = text.slice(0, 137) + '...'
  return text
}

function modules() {
  const result = spawnSync('python3', [MODULES, 'list'], { cwd: REPO, encoding: 'utf8' })
  if (result.status !== 0) throw new Error(result.stderr || 'module listing failed')
  return JSON.parse(result.stdout)
}

function selected(all, mode) {
  if (mode === 'all') return { keep: all, catalog: [] }
  const keep = all.filter(module => mode === 'must'
    ? module.retention === 'must'
    : module.retention === 'must' || module.retention === 'profile')
  const slugs = new Set(keep.map(module => module.slug))
  return { keep, catalog: all.filter(module => !slugs.has(module.slug)) }
}

function row(tool, all, mode) {
  const { keep, catalog } = selected(all, mode)
  const desc = keep.reduce((n, module) => n + (tool === 'cursor'
    ? shortDescription(module.description).length
    : String(module.description || '').length), 0)
  const routedChars = catalog.length ? RESOLVER_DESCRIPTION.length : 0
  const routeChars = catalog.length && ['claude', 'pi'].includes(tool) ? GENERIC_DESCRIPTION.length : 0
  const chars = desc + routedChars + routeChars
  const estimate = Math.round(chars / 4)
  const budget = mode === 'must' ? BUDGETS.must[tool] : null
  return {
    indexed: keep.length + (catalog.length ? 1 : 0),
    description_chars: chars,
    estimated_tokens: estimate,
    budget,
    within_budget: budget == null ? true : estimate <= budget,
  }
}

function build() {
  const all = modules()
  const tools = {}
  for (const tool of TOOLS) {
    tools[tool] = {}
    for (const mode of ['all', 'profile', 'must']) tools[tool][mode] = row(tool, all, mode)
  }
  return {
    schema_version: 1,
    measurement: 'estimate',
    estimate_method: 'indexed description characters divided by four',
    module_count: all.length,
    tools,
  }
}

function main() {
  const report = build()
  const failed = TOOLS.filter(tool => !report.tools[tool].must.within_budget)
  if (process.argv.includes('--json')) process.stdout.write(JSON.stringify(report) + '\n')
  else {
    for (const tool of TOOLS) {
      const value = report.tools[tool].must
      console.log(`${tool}: ${value.indexed} indexed; ~${value.estimated_tokens} tokens; budget ${value.budget}`)
    }
  }
  if (failed.length) {
    console.error(`context footprint budget exceeded: ${failed.join(', ')}`)
    process.exitCode = 1
  }
}

if (require.main === module) main()
module.exports = { build }
