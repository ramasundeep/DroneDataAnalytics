// Navigation model. Live pages are backed by real API endpoints; planned
// pages render an honest placeholder pointing at the roadmap.

export interface LiveNavItem {
  kind: 'live';
  path: string;
  label: string;
}

export interface PlannedNavItem {
  kind: 'planned';
  path: string;
  label: string;
  phase: string;
}

export type NavItem = LiveNavItem | PlannedNavItem;

export const NAV_ITEMS: NavItem[] = [
  { kind: 'live', path: '/', label: 'System status' },
  { kind: 'live', path: '/platforms', label: 'Platforms' },
  { kind: 'live', path: '/areas', label: 'Areas' },
  { kind: 'live', path: '/scenarios', label: 'Scenarios' },
  { kind: 'planned', path: '/sessions', label: 'Sessions', phase: '4' },
  { kind: 'planned', path: '/live', label: 'Live monitor', phase: '4' },
  { kind: 'planned', path: '/replay', label: 'Replay', phase: '3/4' },
  { kind: 'planned', path: '/trainees', label: 'Trainees', phase: '4' },
  { kind: 'planned', path: '/fleet', label: 'Fleet', phase: '5' },
  { kind: 'planned', path: '/maintainer', label: 'Maintainer', phase: '6' },
];
