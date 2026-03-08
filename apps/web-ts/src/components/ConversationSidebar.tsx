import { MessageSquare, Plus, Trash2, MoreHorizontal, House } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

export interface Conversation {
  id: string;
  preview: string;
  timestamp: Date;
  isActive?: boolean;
}

function timeAgo(date: Date): string {
  const days = Math.floor((Date.now() - date.getTime()) / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

interface ConversationSidebarProps {
  activeConversationId: string | null;
  conversations: Conversation[];
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
  onClearAll: () => void;
}

export default function ConversationSidebar({
  activeConversationId,
  conversations,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onClearAll,
}: ConversationSidebarProps) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const displayName = user?.email?.split("@")[0] ?? "User";
  const displayEmail = user?.email ?? "";
  const [showClearDialog, setShowClearDialog] = useState(false);

  return (
    <aside className="w-72 border-r bg-card flex flex-col h-screen flex-shrink-0 overflow-hidden">
      {/* Branding */}
      <div className="px-5 pt-5 pb-4 flex items-center gap-2.5">
        <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
          <span className="text-sm font-bold text-primary-foreground">P</span>
        </div>
        <span className="font-semibold text-base tracking-tight">PingHR</span>
      </div>

      {/* New Conversation + More menu */}
      <div className="px-4 pb-3 flex items-center gap-1.5">
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
      <div className="px-4 pb-3">
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 text-sm font-normal h-9"
          onClick={() => {
            onNewConversation();
            navigate("/chat");
          }}
        >
          <House className="h-4 w-4" />
          Home
        </Button>
      </div>

      {/* Clear all confirmation dialog */}
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
                <div className="flex items-center gap-1 mt-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                  <span className="text-xs text-muted-foreground">{timeAgo(conv.timestamp)}</span>
                </div>
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
