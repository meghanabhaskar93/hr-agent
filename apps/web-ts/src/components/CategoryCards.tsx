import { motion } from "framer-motion";
import {
  CalendarDays,
  DollarSign,
  Heart,
  Building2,
  Anchor,
  FileText,
  Briefcase,
  Shield,
} from "lucide-react";

const categories = [
  {
    icon: CalendarDays,
    title: "Leave & Time Off",
    description: "Annual leave, sick days, parental leave",
    prompt: "What is the annual leave policy?",
    bgColor: "bg-warning/10",
    iconColor: "text-warning",
    borderColor: "border-warning/20",
  },
  {
    icon: DollarSign,
    title: "Payroll & Pay",
    description: "Pay dates, payslips, expenses",
    prompt: "When is the next pay day?",
    bgColor: "bg-success/10",
    iconColor: "text-success",
    borderColor: "border-success/20",
  },
  {
    icon: Heart,
    title: "Benefits",
    description: "Health, pension, gym, perks",
    prompt: "What health benefits do we have?",
    bgColor: "bg-info/10",
    iconColor: "text-info",
    borderColor: "border-info/20",
  },
  {
    icon: Building2,
    title: "Company Policy",
    description: "Remote work, code of conduct, hours",
    prompt: "What is the remote work policy?",
    bgColor: "bg-primary/10",
    iconColor: "text-primary",
    borderColor: "border-primary/20",
  },
  {
    icon: Anchor,
    title: "Onboarding",
    description: "First day prep, probation, setup",
    prompt: "What should I know for my first day?",
    bgColor: "bg-destructive/10",
    iconColor: "text-destructive",
    borderColor: "border-destructive/20",
  },
  {
    icon: FileText,
    title: "Documents",
    description: "Letters, payslips, tax forms",
    prompt: "How do I access my payslips?",
    bgColor: "bg-info/10",
    iconColor: "text-info",
    borderColor: "border-info/20",
  },
  {
    icon: Briefcase,
    title: "Career & Growth",
    description: "Internal jobs, promotions, reviews",
    prompt: "When is the next performance review?",
    bgColor: "bg-primary/10",
    iconColor: "text-primary",
    borderColor: "border-primary/20",
  },
  {
    icon: Shield,
    title: "Wellbeing & Support",
    description: "EAP, mental health, occupational health",
    prompt: "What mental health resources are available?",
    bgColor: "bg-success/10",
    iconColor: "text-success",
    borderColor: "border-success/20",
  },
];

interface CategoryCardsProps {
  onSelectCategory: (prompt: string) => void;
}

export default function CategoryCards({ onSelectCategory }: CategoryCardsProps) {
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
