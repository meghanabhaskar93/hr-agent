import { MessageSquare, Plus, Trash2, MoreHorizontal, BarChart3, Inbox, PanelLeftClose, PanelLeft, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { NavLink } from "@/components/NavLink";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import type { Conversation } from "@/components/ConversationSidebar";

function timeAgo(date: Date): string {
  const days = Math.floor((Date.now() - date.getTime()) / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

interface HRConversationSidebarProps {
  activeConversationId: string | null;
  conversations: Conversation[];
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
  onClearAll: () => void;
  assignedCount?: number;
}

export default function HRConversationSidebar({
  activeConversationId,
  conversations,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onClearAll,
  assignedCount = 0,
}: HRConversationSidebarProps) {
  const { user, signOut } = useAuth();
  const displayName = user?.email?.split("@")[0] ?? "User";
  const displayEmail = user?.email ?? "";
  const [showClearDialog, setShowClearDialog] = useState(false);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("hr-sidebar-collapsed") === "true");

  const toggleCollapsed = (value: boolean) => {
    setCollapsed(value);
    localStorage.setItem("hr-sidebar-collapsed", String(value));
  };

  if (collapsed) {
    return (
      <aside className="relative w-16 border-r bg-card flex flex-col h-screen flex-shrink-0 overflow-visible transition-all duration-200 group/sidebar">
        {/* Branding - icon only */}
        <div className="px-3 pt-5 pb-4 flex items-center justify-center">
          <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
            <span className="text-sm font-bold text-primary-foreground">P</span>
          </div>
        </div>
        {/* Edge toggle button */}
        <button
          onClick={() => toggleCollapsed(false)}
          className="absolute -right-3 top-7 z-50 h-6 w-6 rounded-full border bg-card shadow-sm flex items-center justify-center opacity-0 group-hover/sidebar:opacity-100 hover:bg-accent transition-all"
        >
          <ChevronRight className="h-3 w-3 text-muted-foreground" />
        </button>

        {/* Nav Links - icons only */}
        <div className="px-2 pb-3 space-y-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <NavLink
                to="/hr-chat"
                end
                className="flex items-center justify-center p-2 rounded-lg hover:bg-muted/60 transition-colors"
                activeClassName="bg-accent text-accent-foreground"
              >
                <MessageSquare className="h-4 w-4" />
              </NavLink>
            </TooltipTrigger>
            <TooltipContent side="right">Chat</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <NavLink
                to="/hr-ops"
                end
                className="relative flex items-center justify-center p-2 rounded-lg hover:bg-muted/60 transition-colors"
                activeClassName="bg-accent text-accent-foreground"
              >
                <Inbox className="h-4 w-4" />
                {assignedCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 h-4 min-w-4 px-1 rounded-full bg-destructive text-destructive-foreground text-[9px] font-bold flex items-center justify-center">
                    {assignedCount}
                  </span>
                )}
              </NavLink>
            </TooltipTrigger>
            <TooltipContent side="right">HR Ops</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <NavLink
                to="/audit-log"
                end
                className="flex items-center justify-center p-2 rounded-lg hover:bg-muted/60 transition-colors"
                activeClassName="bg-accent text-accent-foreground"
              >
                <BarChart3 className="h-4 w-4" />
              </NavLink>
            </TooltipTrigger>
            <TooltipContent side="right">Audit Log</TooltipContent>
          </Tooltip>
        </div>

        <div className="border-t mx-2" />

        {/* New conversation - icon only */}
        <div className="px-2 py-3 flex justify-center">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline" size="icon" className="h-10 w-10" onClick={onNewConversation}>
                <Plus className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">New conversation</TooltipContent>
          </Tooltip>
        </div>

        {/* Conversation list - icons only */}
        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          {conversations.map((conv) => (
            <Tooltip key={conv.id}>
              <TooltipTrigger asChild>
                <button
                  onClick={() => onSelectConversation(conv.id)}
                  className={`w-full flex items-center justify-center p-2 rounded-lg transition-colors ${
                    activeConversationId === conv.id
                      ? "bg-accent text-accent-foreground"
                      : "hover:bg-muted/60"
                  }`}
                >
                  <MessageSquare className="h-4 w-4 text-muted-foreground" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">{conv.preview}</TooltipContent>
            </Tooltip>
          ))}
        </div>

        {/* User avatar */}
        <div className="border-t px-2 py-3 flex justify-center">
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={signOut}
                className="w-full flex justify-center py-1"
              >
                <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0 hover:opacity-80 transition-opacity">
                  <span className="text-xs font-semibold text-primary-foreground">
                    {displayName.charAt(0).toUpperCase()}
                  </span>
                </div>
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">Sign out ({displayEmail})</TooltipContent>
          </Tooltip>
        </div>
      </aside>
    );
  }

  return (
    <aside className="relative w-72 border-r bg-card flex flex-col h-screen flex-shrink-0 overflow-visible transition-all duration-200 group/sidebar">
      {/* Edge toggle button */}
      <button
        onClick={() => toggleCollapsed(true)}
        className="absolute -right-3 top-7 z-50 h-6 w-6 rounded-full border bg-card shadow-sm flex items-center justify-center opacity-0 group-hover/sidebar:opacity-100 hover:bg-accent transition-all"
      >
        <ChevronLeft className="h-3 w-3 text-muted-foreground" />
      </button>
      {/* Branding */}
      <div className="px-5 pt-5 pb-4 flex items-center gap-2.5">
        <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
          <span className="text-sm font-bold text-primary-foreground">P</span>
        </div>
        <div className="flex-1">
          <span className="font-semibold text-base tracking-tight">PingHR</span>
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium">HR Portal</p>
        </div>
      </div>

      {/* HR Nav Links */}
      <div className="px-3 pb-3 space-y-0.5">
        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-3 mb-1.5">
          Workspace
        </p>
        <NavLink
          to="/hr-chat"
          end
          className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm hover:bg-muted/60 transition-colors"
          activeClassName="bg-accent text-accent-foreground font-medium"
        >
          <MessageSquare className="h-4 w-4" />
          <span>Chat</span>
        </NavLink>
        <NavLink
          to="/hr-ops"
          end
          className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm hover:bg-muted/60 transition-colors"
          activeClassName="bg-accent text-accent-foreground font-medium"
        >
          <Inbox className="h-4 w-4" />
          <span>HR Ops</span>
          {assignedCount > 0 && (
            <Badge variant="secondary" className="ml-auto h-5 min-w-5 px-1.5 text-[10px] font-bold">
              {assignedCount}
            </Badge>
          )}
        </NavLink>
        <NavLink
          to="/audit-log"
          end
          className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm hover:bg-muted/60 transition-colors"
          activeClassName="bg-accent text-accent-foreground font-medium"
        >
          <BarChart3 className="h-4 w-4" />
          <span>Audit Log</span>
        </NavLink>
      </div>

      <div className="border-t mx-3" />

      {/* New Conversation + More menu */}
      <div className="px-4 py-3 flex items-center gap-1.5">
        <Button
          variant="outline"
          className="flex-1 justify-start gap-2 text-sm font-normal h-10"
          onClick={onNewConversation}
        >
          <Plus className="h-4 w-4" />
          New conversation
        </Button>
        {conversations.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-10 w-10 flex-shrink-0">
                <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem
                className="text-destructive focus:text-destructive gap-2 text-sm"
                onClick={() => setShowClearDialog(true)}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Clear all conversations
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      <AlertDialog open={showClearDialog} onOpenChange={setShowClearDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Clear all conversations?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete all {conversations.length} conversations. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                onClearAll();
                setShowClearDialog(false);
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Clear all
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto px-3 space-y-0.5">
        {conversations.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-6">No conversations yet</p>
        )}
        {conversations.map((conv) => (
          <div key={conv.id} className="group relative">
            <button
              onClick={() => onSelectConversation(conv.id)}
              className={`w-full flex items-start gap-2.5 px-3 py-2.5 rounded-lg text-left transition-colors ${
                activeConversationId === conv.id
                  ? "bg-accent text-accent-foreground"
                  : "hover:bg-muted/60"
              }`}
            >
              <MessageSquare className="h-4 w-4 mt-0.5 flex-shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <p className="text-sm truncate pr-6">{conv.preview}</p>
                <span className="text-xs text-muted-foreground">{timeAgo(conv.timestamp)}</span>
              </div>
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDeleteConversation(conv.id);
              }}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md opacity-0 group-hover:opacity-100 hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
              title="Delete conversation"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>

      {/* User Profile */}
      <div className="border-t px-4 py-3">
        <button
          onClick={signOut}
          className="w-full flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-muted/60 transition-colors"
        >
          <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
            <span className="text-xs font-semibold text-primary-foreground">
              {displayName.charAt(0).toUpperCase()}
            </span>
          </div>
          <div className="min-w-0 flex-1 text-left">
            <p className="text-sm font-medium truncate capitalize">{displayName}</p>
            <p className="text-xs text-muted-foreground truncate">{displayEmail}</p>
          </div>
        </button>
      </div>
    </aside>
  );
}
