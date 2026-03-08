import { useState } from "react";
import { Search, ClipboardList, BarChart3, MessageSquare, ChevronRight, Building2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { NavLink } from "@/components/NavLink";
import { mockEmployees, Employee } from "@/data/mockEmployees";
import { useAuth } from "@/contexts/AuthContext";

interface HRSidebarProps {
  selectedEmployee: Employee | null;
  onSelectEmployee: (emp: Employee) => void;
}

export default function HRSidebar({ selectedEmployee, onSelectEmployee }: HRSidebarProps) {
  const [search, setSearch] = useState("");
  const { signOut } = useAuth();

  const filtered = mockEmployees.filter(
    (e) =>
      e.name.toLowerCase().includes(search.toLowerCase()) ||
      e.role.toLowerCase().includes(search.toLowerCase()) ||
      e.department.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <aside className="w-72 border-r bg-card flex flex-col h-full overflow-hidden">
      {/* Branding */}
      <div className="p-5 text-center border-b">
        <div className="h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center mx-auto mb-2">
          <Building2 className="h-6 w-6 text-primary" />
        </div>
        <h2 className="font-bold text-base">ACME Corp</h2>
        <p className="text-xs text-muted-foreground">HR Assistant Portal</p>
      </div>

      {/* Employee Search */}
      <div className="px-4 pt-4 pb-2">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
          Select Employee
        </p>
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search employees..."
            className="pl-8 h-9 text-sm"
          />
        </div>
      </div>

      {/* Employee List */}
      <div className="flex-1 overflow-y-auto px-2 py-1">
        {filtered.map((emp) => (
          <button
            key={emp.id}
            onClick={() => onSelectEmployee(emp)}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-sm transition-colors mb-0.5 ${
              selectedEmployee?.id === emp.id
                ? "bg-accent text-accent-foreground"
                : "hover:bg-muted/60"
            }`}
          >
            <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
              <span className="text-xs font-semibold text-primary">{emp.initials}</span>
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-medium text-sm truncate">{emp.name}</p>
              <p className="text-xs text-muted-foreground truncate">{emp.role}</p>
            </div>
            {selectedEmployee?.id === emp.id && (
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
            )}
          </button>
        ))}
        {filtered.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">No employees found</p>
        )}
      </div>

      {/* Profile Card */}
      {selectedEmployee && (
        <div className="border-t px-4 py-4">
          <div className="text-center mb-3">
            <div className="h-12 w-12 rounded-full bg-primary flex items-center justify-center mx-auto mb-2">
              <span className="text-sm font-bold text-primary-foreground">{selectedEmployee.initials}</span>
            </div>
            <p className="font-semibold text-sm">{selectedEmployee.name}</p>
            <p className="text-xs text-muted-foreground">{selectedEmployee.role}</p>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <div>
              <p className="text-muted-foreground uppercase tracking-wider font-medium" style={{ fontSize: "10px" }}>Department</p>
              <p className="font-medium">{selectedEmployee.department}</p>
            </div>
            <div>
              <p className="text-muted-foreground uppercase tracking-wider font-medium" style={{ fontSize: "10px" }}>Location</p>
              <p className="font-medium">{selectedEmployee.location}</p>
            </div>
            <div>
              <p className="text-muted-foreground uppercase tracking-wider font-medium" style={{ fontSize: "10px" }}>Tenure</p>
              <p className="font-medium">{selectedEmployee.tenure}</p>
            </div>
            <div>
              <p className="text-muted-foreground uppercase tracking-wider font-medium" style={{ fontSize: "10px" }}>Manager</p>
              <p className="font-medium">{selectedEmployee.manager}</p>
            </div>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="border-t px-3 py-3 space-y-0.5">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-2 mb-2">
          ⚡ Quick Actions
        </p>
        <NavLink
          to="/chat"
          end
          className="flex items-center gap-2 px-2.5 py-2 rounded-lg text-sm hover:bg-muted/60 transition-colors"
          activeClassName="bg-accent text-accent-foreground font-medium"
        >
          <MessageSquare className="h-4 w-4" />
          <span>PingHR Chat</span>
        </NavLink>
        <NavLink
          to="/hr-queue"
          end
          className="flex items-center gap-2 px-2.5 py-2 rounded-lg text-sm hover:bg-muted/60 transition-colors"
          activeClassName="bg-accent text-accent-foreground font-medium"
        >
          <ClipboardList className="h-4 w-4" />
          <span>HR Queue</span>
        </NavLink>
        <NavLink
          to="/audit-log"
          end
          className="flex items-center gap-2 px-2.5 py-2 rounded-lg text-sm hover:bg-muted/60 transition-colors"
          activeClassName="bg-accent text-accent-foreground font-medium"
        >
          <BarChart3 className="h-4 w-4" />
          <span>Audit Log</span>
        </NavLink>
      </div>

      {/* Sign out */}
      <div className="border-t px-3 py-3">
        <button
          onClick={signOut}
          className="w-full text-left px-2.5 py-2 rounded-lg text-sm text-muted-foreground hover:bg-muted/60 transition-colors"
        >
          Sign Out
        </button>
      </div>
    </aside>
  );
}
