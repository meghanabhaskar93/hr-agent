import { motion } from "framer-motion";
import { Users, BookOpen, PenTool, BarChart3 } from "lucide-react";

const categories = [
  {
    icon: Users,
    title: "Employee Lookup",
    description: "Search employee details, department, manager",
    prompt: "I need to look up an employee",
    bgColor: "bg-primary/10",
    iconColor: "text-primary",
    borderColor: "border-primary/20",
  },
  {
    icon: BookOpen,
    title: "Policy Reference",
    description: "Look up internal policies to answer tickets",
    prompt: "What is our parental leave policy?",
    bgColor: "bg-info/10",
    iconColor: "text-info",
    borderColor: "border-info/20",
  },
  {
    icon: PenTool,
    title: "Draft Response",
    description: "AI helps draft replies to escalated queries",
    prompt: "I need to draft a response for an employee query",
    bgColor: "bg-warning/10",
    iconColor: "text-warning",
    borderColor: "border-warning/20",
  },
  {
    icon: BarChart3,
    title: "Analytics & Insights",
    description: "Escalation trends, resolution times, top topics",
    prompt: "What are the top escalation categories this month?",
    bgColor: "bg-success/10",
    iconColor: "text-success",
    borderColor: "border-success/20",
  },
];

interface HRCategoryCardsProps {
  onSelectCategory: (prompt: string) => void;
}

export default function HRCategoryCards({ onSelectCategory }: HRCategoryCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-4 max-w-2xl mx-auto">
      {categories.map((cat, i) => (
        <motion.button
          key={cat.title}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.04, duration: 0.3 }}
          onClick={() => onSelectCategory(cat.prompt)}
          className={`flex items-center gap-3 px-5 py-4 rounded-xl border ${cat.borderColor} ${cat.bgColor} text-left hover:shadow-soft transition-all duration-200 group`}
        >
          <cat.icon className={`h-5 w-5 ${cat.iconColor} flex-shrink-0`} />
          <div className="min-w-0">
            <p className="text-sm font-semibold">{cat.title}</p>
            <p className="text-xs text-muted-foreground">{cat.description}</p>
          </div>
        </motion.button>
      ))}
    </div>
  );
}
