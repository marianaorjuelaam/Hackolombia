/**
 * CENTRALIZED BRAND CONFIGURATION
 * All user-facing product name, copy, logo, and colors live here.
 * Internal pipeline names (s08f_cultiva_allocation_engine, etc.) are NOT renamed here.
 */

export const brand = {
  name: 'MAIZEVR',
  productName: 'MAIZEVR',
  productNameFull: 'MAIZEVR Intelligence',
  tagline: 'Intelligence from genome to field.',
  taglineSub: 'Identify the maize lines most likely to succeed before committing resources to the next breeding stage.',
  heroStatement: '500 candidates. 50 advancement slots. Which lines move forward?',
  ctaPrimary: 'Build My Next Generation',
  ctaSecondary: 'Explore Candidates',
  footerCopy: '© 2024 MAIZEVR Intelligence. Genomic decision platform.',

  // Official logo asset path — served from /public
  logo: '/maizevr-logo.png',

  // Navigation labels — rename here only, never scattered in components
  nav: {
    overview: 'Overview',
    copilot: 'Field Copilot',
    lines: 'Lines',
    gems: 'Hidden Gems',
    cohort: 'Build Cohort',
    intelligence: 'Model Intelligence',
    settings: 'Settings',
  },

  // JS color references (used where Tailwind class generation isn't possible)
  // These resolve to the correct theme value at runtime via CSS variables.
  // For static references only — prefer Tailwind classes in components.
  colors: {
    // These match the dark-mode defaults; CSS variables override in light mode
    accent: '#4ade80',
    accentDim: '#22c55e',
    amber: '#fbbf24',
    danger: '#f87171',
  },

  // Product copy — centralized for easy localization
  copy: {
    copilotHeadline: 'Your AI assistant surfaces the lines that deserve attention.',
    copilotSub: 'One decision at a time. Work through today\'s queue.',
    gemsHeadline: 'Find the overlooked opportunities.',
    gemsSub: 'Lines whose genomic evidence outpaces their observed performance.',
    cohortHeadline: 'Build Your Next Generation',
    cohortSub: 'Select the optimal set of lines to advance — backed by model evidence.',
    intelligenceHeadline: 'Model Intelligence',
    intelligenceSub: 'Understand the evidence behind every prediction.',
  },

  // Domain constants
  domain: {
    totalCandidates: 500,
    advancementSlots: 50,
    primaryTrait: 'Grain Yield',
    traitUnit: 't/ha',
    populationLabels: { C1: 'Population C1', C2: 'Population C2' },
  },
} as const

export type Brand = typeof brand
