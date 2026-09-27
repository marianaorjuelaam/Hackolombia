import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Crosshair, Rows3, Gem, Layers, Brain,
  Settings, ChevronLeft, ChevronRight, Sun, Moon, Menu
} from 'lucide-react'
import { brand } from '@/config/brand'
import { useTheme } from '@/hooks/useTheme'
import { cn } from '@/lib/utils'

const navItems = [
  { path: '/', label: brand.nav.overview, icon: LayoutDashboard, exact: true },
  { path: '/copilot', label: brand.nav.copilot, icon: Crosshair },
  { path: '/lines', label: brand.nav.lines, icon: Rows3 },
  { path: '/gems', label: brand.nav.gems, icon: Gem },
  { path: '/cohort', label: brand.nav.cohort, icon: Layers },
  { path: '/intelligence', label: brand.nav.intelligence, icon: Brain },
]

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const navigate = useNavigate()

  return (
    <div className="flex h-screen bg-surface-0 overflow-hidden">
      {/* Mobile overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-30 lg:hidden"
            onClick={() => setMobileOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        animate={{ width: collapsed ? 64 : 240 }}
        transition={{ duration: 0.25, ease: 'easeInOut' }}
        className={cn(
          'hidden lg:flex flex-col bg-surface-1 border-r border-border-subtle z-20 flex-shrink-0',
        )}
      >
        <SidebarContent collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} navigate={navigate} />
      </motion.aside>

      {/* Mobile sidebar */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.aside
            initial={{ x: -240 }}
            animate={{ x: 0 }}
            exit={{ x: -240 }}
            transition={{ duration: 0.25 }}
            className="fixed left-0 top-0 bottom-0 w-60 bg-surface-1 border-r border-border-subtle z-40 flex flex-col lg:hidden"
          >
            <SidebarContent collapsed={false} onToggle={() => setMobileOpen(false)} navigate={navigate} />
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile topbar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border-subtle bg-surface-1 lg:hidden">
          <button onClick={() => setMobileOpen(true)} className="text-text-secondary hover:text-text-primary">
            <Menu size={20} />
          </button>
          <img src={brand.logo} alt={brand.productName} className="h-6 w-auto object-contain max-w-[120px]" />
        </div>

        <main className="flex-1 overflow-y-auto">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="h-full"
          >
            <Outlet />
          </motion.div>
        </main>
      </div>
    </div>
  )
}

function SidebarContent({
  collapsed,
  onToggle,
  navigate,
}: {
  collapsed: boolean
  onToggle: () => void
  navigate: (path: string) => void
}) {
  const { theme, toggle } = useTheme()

  return (
    <>
      {/* Logo */}
      <div className={cn(
        'flex items-center border-b border-border-subtle flex-shrink-0',
        collapsed ? 'px-3 py-4 justify-center' : 'px-5 py-4'
      )}>
        <AnimatePresence mode="wait">
          {collapsed ? (
            <motion.div
              key="collapsed"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="w-7 h-7 rounded-md bg-brand-400/10 border border-brand-400/20 flex items-center justify-center flex-shrink-0"
            >
              <span className="text-brand-400 text-xs font-black">M</span>
            </motion.div>
          ) : (
            <motion.div
              key="expanded"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <img
                src={brand.logo}
                alt={brand.productName}
                className="h-8 w-auto object-contain max-w-[160px]"
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 overflow-y-auto overflow-x-hidden">
        {navItems.map(item => (
          <SidebarItem key={item.path} item={item} collapsed={collapsed} />
        ))}
      </nav>

      {/* Bottom */}
      <div className="border-t border-border-subtle py-3">
        <NavLink
          to="/settings"
          className={({ isActive }) => cn(
            'flex items-center gap-3 mx-2 px-3 py-2 rounded-lg transition-all duration-150 text-text-muted hover:text-text-secondary hover:bg-surface-3',
            isActive && 'text-text-secondary bg-surface-3',
            collapsed && 'justify-center'
          )}
        >
          <Settings size={16} />
          {!collapsed && <span className="text-xs">Settings</span>}
        </NavLink>

        <button
          onClick={toggle}
          className={cn(
            'flex items-center gap-3 mx-2 px-3 py-2 rounded-lg transition-all duration-150 text-text-muted hover:text-text-secondary hover:bg-surface-3 w-[calc(100%-16px)]',
            collapsed && 'justify-center'
          )}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          {!collapsed && <span className="text-xs">{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>}
        </button>

        <button
          onClick={onToggle}
          className={cn(
            'flex items-center gap-3 mx-2 px-3 py-2 rounded-lg transition-all duration-150 text-text-muted hover:text-text-secondary hover:bg-surface-3 w-[calc(100%-16px)]',
            collapsed && 'justify-center'
          )}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          {!collapsed && <span className="text-xs">Collapse</span>}
        </button>
      </div>
    </>
  )
}

function SidebarItem({ item, collapsed }: { item: typeof navItems[0]; collapsed: boolean }) {
  return (
    <NavLink
      to={item.path}
      end={item.exact}
      className={({ isActive }) => cn(
        'flex items-center gap-3 mx-2 px-3 py-2.5 rounded-lg transition-all duration-150 group relative',
        isActive
          ? 'bg-brand-400/10 text-brand-400 border border-brand-400/15'
          : 'text-text-secondary hover:text-text-primary hover:bg-surface-3',
        collapsed && 'justify-center'
      )}
    >
      {({ isActive }) => (
        <>
          <item.icon size={16} className={cn('flex-shrink-0', isActive && 'text-brand-400')} />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                className="text-sm font-medium whitespace-nowrap overflow-hidden"
              >
                {item.label}
              </motion.span>
            )}
          </AnimatePresence>
          {collapsed && (
            <div className="absolute left-full ml-3 px-2 py-1 bg-surface-3 text-text-primary text-xs rounded-md border border-border-default opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50 shadow-xl">
              {item.label}
            </div>
          )}
        </>
      )}
    </NavLink>
  )
}
