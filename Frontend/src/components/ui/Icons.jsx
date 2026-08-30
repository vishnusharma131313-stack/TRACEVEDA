/*
 * Inline icon set.
 *
 * Deliberately not an icon package: the project ships no icon dependency, and
 * adding one for ~16 glyphs is weight the demo does not need. Every icon is a
 * 24x24 stroked path so they sit on one optical grid.
 */

const base = {
  width: '1em',
  height: '1em',
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
  focusable: false,
}

const make = (paths) =>
  function Icon({ className = '', size, ...rest }) {
    return (
      <svg
        {...base}
        className={className}
        style={size ? { width: size, height: size } : undefined}
        {...rest}
      >
        {paths}
      </svg>
    )
  }

export const IconGrid = make(
  <>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
  </>,
)

export const IconBlocks = make(
  <>
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
    <path d="m3.3 7 8.7 5 8.7-5" />
    <path d="M12 22V12" />
  </>,
)

export const IconRoute = make(
  <>
    <circle cx="6" cy="19" r="2.5" />
    <circle cx="18" cy="5" r="2.5" />
    <path d="M8.5 19h5a4 4 0 0 0 0-8h-3a4 4 0 0 1 0-8h5" />
  </>,
)

export const IconSignal = make(
  <>
    <path d="M4.9 4.9a10 10 0 0 0 0 14.2" />
    <path d="M19.1 4.9a10 10 0 0 1 0 14.2" />
    <path d="M8.4 8.4a5 5 0 0 0 0 7.2" />
    <path d="M15.6 8.4a5 5 0 0 1 0 7.2" />
    <circle cx="12" cy="12" r="1.5" />
  </>,
)

export const IconShield = make(<path d="M12 3 5 6v5.5c0 4.3 2.9 8.3 7 9.5 4.1-1.2 7-5.2 7-9.5V6z" />)

export const IconShieldCheck = make(
  <>
    <path d="M12 3 5 6v5.5c0 4.3 2.9 8.3 7 9.5 4.1-1.2 7-5.2 7-9.5V6z" />
    <path d="m9 12 2 2 4-4" />
  </>,
)

export const IconShieldAlert = make(
  <>
    <path d="M12 3 5 6v5.5c0 4.3 2.9 8.3 7 9.5 4.1-1.2 7-5.2 7-9.5V6z" />
    <path d="M12 8.5v4" />
    <path d="M12 16h.01" />
  </>,
)

export const IconLink = make(
  <>
    <path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.2 1.1" />
    <path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.2-1.1" />
  </>,
)

export const IconSearch = make(
  <>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </>,
)

export const IconChevronDown = make(<path d="m6 9 6 6 6-6" />)
export const IconChevronRight = make(<path d="m9 6 6 6-6 6" />)
export const IconArrowLeft = make(
  <>
    <path d="M19 12H5" />
    <path d="m12 19-7-7 7-7" />
  </>,
)
export const IconArrowRight = make(
  <>
    <path d="M5 12h14" />
    <path d="m12 5 7 7-7 7" />
  </>,
)

export const IconCheck = make(<path d="m4 12.5 5 5L20 6.5" />)
export const IconX = make(
  <>
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </>,
)

export const IconCopy = make(
  <>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15V5a2 2 0 0 1 2-2h10" />
  </>,
)

export const IconLeaf = make(
  <>
    <path d="M11 20A7 7 0 0 1 4 13c0-5 4-9 16-9 0 10-4 14-9 14z" />
    <path d="M4 21c3-6 7-9 12-10.5" />
  </>,
)

export const IconFlask = make(
  <>
    <path d="M9 3v6.2L4.6 17A2 2 0 0 0 6.3 20h11.4a2 2 0 0 0 1.7-3L15 9.2V3" />
    <path d="M8 3h8" />
    <path d="M7 15h10" />
  </>,
)

export const IconFactory = make(
  <>
    <path d="M3 21V10l6 4V10l6 4V7h3a1 1 0 0 1 1 1v13z" />
    <path d="M3 21h18" />
  </>,
)

export const IconTruck = make(
  <>
    <path d="M3 16V6a1 1 0 0 1 1-1h9v11" />
    <path d="M13 9h4l3 3.5V16" />
    <circle cx="7.5" cy="17.5" r="2" />
    <circle cx="17" cy="17.5" r="2" />
  </>,
)

export const IconPill = make(
  <>
    <rect x="2.5" y="8.5" width="19" height="7" rx="3.5" transform="rotate(-45 12 12)" />
    <path d="M8.8 8.8 15.2 15.2" />
  </>,
)

export const IconAlertTriangle = make(
  <>
    <path d="M10.3 4.3 2.6 17.4A2 2 0 0 0 4.3 20.4h15.4a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z" />
    <path d="M12 9.5v4" />
    <path d="M12 17h.01" />
  </>,
)

export const IconClock = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5.5l3.5 2" />
  </>,
)

export const IconDatabase = make(
  <>
    <ellipse cx="12" cy="6" rx="8" ry="3" />
    <path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6" />
    <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
  </>,
)

export const IconMenu = make(
  <>
    <path d="M4 7h16" />
    <path d="M4 12h16" />
    <path d="M4 17h16" />
  </>,
)

export const IconLogout = make(
  <>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="m16 17 5-5-5-5" />
    <path d="M21 12H9" />
  </>,
)

export const IconRefresh = make(
  <>
    <path d="M20 11A8 8 0 0 0 6.3 6.3L4 8.5" />
    <path d="M4 4v4.5h4.5" />
    <path d="M4 13a8 8 0 0 0 13.7 4.7L20 15.5" />
    <path d="M20 20v-4.5h-4.5" />
  </>,
)

export const IconQr = make(
  <>
    <rect x="3.5" y="3.5" width="6" height="6" rx="1" />
    <rect x="14.5" y="3.5" width="6" height="6" rx="1" />
    <rect x="3.5" y="14.5" width="6" height="6" rx="1" />
    <path d="M14.5 14.5h2.5v2.5h-2.5z" />
    <path d="M20.5 14.5v2" />
    <path d="M17.5 20.5h3" />
    <path d="M14.5 20.5h.01" />
  </>,
)

export const IconSensorOff = make(
  <>
    <path d="M4.9 4.9a10 10 0 0 0 0 14.2" />
    <path d="M8.4 8.4a5 5 0 0 0 0 7.2" />
    <path d="m3 3 18 18" />
    <path d="M19.1 4.9a10 10 0 0 1 1.4 12" />
  </>,
)

export const IconInfo = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5" />
    <path d="M12 8h.01" />
  </>,
)
