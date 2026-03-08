export interface Employee {
  id: string;
  name: string;
  initials: string;
  role: string;
  department: string;
  location: string;
  tenure: string;
  manager: string;
  email: string;
}

export const mockEmployees: Employee[] = [
  {
    id: "1",
    name: "Amanda Foster",
    initials: "AF",
    role: "CTO",
    department: "Executive",
    location: "Berlin",
    tenure: "7y 0m",
    manager: "Jordan Lee",
    email: "amanda.foster@acme.com",
  },
  {
    id: "2",
    name: "Jordan Lee",
    initials: "JL",
    role: "VP Engineering",
    department: "Engineering",
    location: "San Francisco",
    tenure: "4y 6m",
    manager: "Amanda Foster",
    email: "jordan.lee@acme.com",
  },
  {
    id: "3",
    name: "Sam Patel",
    initials: "SP",
    role: "Senior Engineer",
    department: "Engineering",
    location: "New York",
    tenure: "2y 3m",
    manager: "Jordan Lee",
    email: "sam.patel@acme.com",
  },
  {
    id: "4",
    name: "Alex Kim",
    initials: "AK",
    role: "Product Manager",
    department: "Product",
    location: "London",
    tenure: "1y 8m",
    manager: "Riley Park",
    email: "alex.kim@acme.com",
  },
  {
    id: "5",
    name: "Morgan Chen",
    initials: "MC",
    role: "Designer",
    department: "Design",
    location: "Austin",
    tenure: "3y 1m",
    manager: "Casey Liu",
    email: "morgan.chen@acme.com",
  },
  {
    id: "6",
    name: "Riley Park",
    initials: "RP",
    role: "VP Product",
    department: "Product",
    location: "San Francisco",
    tenure: "5y 2m",
    manager: "Amanda Foster",
    email: "riley.park@acme.com",
  },
  {
    id: "7",
    name: "Casey Liu",
    initials: "CL",
    role: "Design Lead",
    department: "Design",
    location: "Seattle",
    tenure: "3y 9m",
    manager: "Amanda Foster",
    email: "casey.liu@acme.com",
  },
  {
    id: "8",
    name: "Taylor Singh",
    initials: "TS",
    role: "Software Engineer",
    department: "Engineering",
    location: "Toronto",
    tenure: "1y 0m",
    manager: "Jordan Lee",
    email: "taylor.singh@acme.com",
  },
];
