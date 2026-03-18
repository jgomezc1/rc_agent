import { useState } from 'react'
import Sidebar from './Sidebar'
import TopNav from './TopNav'

export default function AppShell({
  children, footer,
  onNewChat, conversations,
  activeConversationId, onSelectConversation,
  projects, activeProject, onSelectProject,
  lastRoute, sessionCost,
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="fixed inset-0 flex">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed inset-y-0 left-0 z-30 w-64 transform transition-transform duration-200 ease-in-out
        md:relative md:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <Sidebar
          onNewChat={() => { onNewChat(); setSidebarOpen(false); }}
          conversations={conversations}
          activeId={activeConversationId}
          onSelectConversation={(id) => { onSelectConversation(id); setSidebarOpen(false); }}
          projects={projects}
          activeProject={activeProject}
          onSelectProject={onSelectProject}
          lastRoute={lastRoute}
          sessionCost={sessionCost}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopNav
          activeProject={activeProject}
          lastRoute={lastRoute}
          onMenuClick={() => setSidebarOpen(true)}
        />
        <div className="flex-1 overflow-y-auto min-h-0">
          {children}
        </div>
        {footer && (
          <div className="flex-shrink-0 border-t border-gray-200 bg-white px-3 py-3 sm:px-4">
            <div className="max-w-3xl mx-auto">
              {footer}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
