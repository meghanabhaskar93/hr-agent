import { useState } from "react";
import HRSidebar from "@/components/HRSidebar";
import { Employee } from "@/data/mockEmployees";
import { mockEmployees } from "@/data/mockEmployees";

interface HRLayoutProps {
  children: (selectedEmployee: Employee | null) => React.ReactNode;
}

export default function HRLayout({ children }: HRLayoutProps) {
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(mockEmployees[0]);

  return (
    <div className="min-h-screen flex w-full">
      <HRSidebar
        selectedEmployee={selectedEmployee}
        onSelectEmployee={setSelectedEmployee}
      />
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {children(selectedEmployee)}
      </main>
    </div>
  );
}
