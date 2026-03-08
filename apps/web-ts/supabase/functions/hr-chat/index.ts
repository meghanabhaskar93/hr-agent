import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

const employeeDirectory = [
  { name: "Amanda Foster", role: "CTO", department: "Executive", location: "Berlin", tenure: "7y 0m", manager: "Jordan Lee", email: "amanda.foster@acme.com", salary_band: "$220K–$280K", pto_balance: "14 days remaining", pto_used: "6 days used", sick_leave_balance: "8 days remaining", upcoming_leave: "Mar 24–28 (approved)", last_review: "Q4 2025 — Exceeds Expectations", performance_rating: "4.8/5", start_date: "2019-03-15", benefits_plan: "Premium Health + Dental + Vision", emergency_contact: "Robert Foster (spouse) — 555-0142" },
  { name: "Jordan Lee", role: "VP Engineering", department: "Engineering", location: "San Francisco", tenure: "4y 6m", manager: "Amanda Foster", email: "jordan.lee@acme.com", salary_band: "$190K–$240K", pto_balance: "11 days remaining", pto_used: "9 days used", sick_leave_balance: "7 days remaining", upcoming_leave: "None scheduled", last_review: "Q4 2025 — Meets Expectations", performance_rating: "4.2/5", start_date: "2021-09-01", benefits_plan: "Premium Health + Dental", emergency_contact: "Min-Jun Lee (parent) — 555-0198" },
  { name: "Sam Patel", role: "Senior Engineer", department: "Engineering", location: "New York", tenure: "2y 3m", manager: "Jordan Lee", email: "sam.patel@acme.com", salary_band: "$140K–$175K", pto_balance: "16 days remaining", pto_used: "4 days used", sick_leave_balance: "9 days remaining", upcoming_leave: "Apr 7–11 (pending approval)", last_review: "Q4 2025 — Exceeds Expectations", performance_rating: "4.5/5", start_date: "2023-12-10", benefits_plan: "Standard Health + Dental + Vision", emergency_contact: "Priya Patel (spouse) — 555-0267" },
  { name: "Alex Kim", role: "Product Manager", department: "Product", location: "London", tenure: "1y 8m", manager: "Riley Park", email: "alex.kim@acme.com", salary_band: "$120K–$155K", pto_balance: "12 days remaining", pto_used: "8 days used", sick_leave_balance: "6 days remaining", upcoming_leave: "Mar 17–18 (approved)", last_review: "Q4 2025 — Meets Expectations", performance_rating: "3.9/5", start_date: "2024-07-22", benefits_plan: "Standard Health + Dental", emergency_contact: "Soo-Jin Kim (sibling) — 555-0334" },
  { name: "Morgan Chen", role: "Designer", department: "Design", location: "Austin", tenure: "3y 1m", manager: "Casey Liu", email: "morgan.chen@acme.com", salary_band: "$110K–$140K", pto_balance: "18 days remaining", pto_used: "2 days used", sick_leave_balance: "10 days remaining", upcoming_leave: "None scheduled", last_review: "Q4 2025 — Exceeds Expectations", performance_rating: "4.6/5", start_date: "2023-02-06", benefits_plan: "Premium Health + Dental + Vision", emergency_contact: "Wei Chen (parent) — 555-0411" },
  { name: "Riley Park", role: "VP Product", department: "Product", location: "San Francisco", tenure: "5y 2m", manager: "Amanda Foster", email: "riley.park@acme.com", salary_band: "$185K–$230K", pto_balance: "8 days remaining", pto_used: "12 days used", sick_leave_balance: "5 days remaining", upcoming_leave: "Apr 21–25 (approved)", last_review: "Q4 2025 — Meets Expectations", performance_rating: "4.0/5", start_date: "2020-01-13", benefits_plan: "Premium Health + Dental", emergency_contact: "Jamie Park (spouse) — 555-0488" },
  { name: "Casey Liu", role: "Design Lead", department: "Design", location: "Seattle", tenure: "3y 9m", manager: "Amanda Foster", email: "casey.liu@acme.com", salary_band: "$150K–$185K", pto_balance: "10 days remaining", pto_used: "10 days used", sick_leave_balance: "8 days remaining", upcoming_leave: "Mar 31 (approved, 1 day)", last_review: "Q4 2025 — Exceeds Expectations", performance_rating: "4.4/5", start_date: "2022-06-20", benefits_plan: "Standard Health + Dental + Vision", emergency_contact: "David Liu (spouse) — 555-0556" },
  { name: "Taylor Singh", role: "Software Engineer", department: "Engineering", location: "Toronto", tenure: "1y 0m", manager: "Jordan Lee", email: "taylor.singh@acme.com", salary_band: "$95K–$125K", pto_balance: "19 days remaining", pto_used: "1 day used", sick_leave_balance: "10 days remaining", upcoming_leave: "None scheduled", last_review: "Q4 2025 — Meets Expectations (first review)", performance_rating: "3.8/5", start_date: "2025-03-03", benefits_plan: "Standard Health + Dental", emergency_contact: "Harpreet Singh (parent) — 555-0623" },
];

const systemPrompt = `You are PingHR, an AI assistant for the HR operations team at Acme Corp. You are speaking to an **authorized HR professional** who has **full access** to all employee records, PTO balances, leave schedules, salary bands, performance reviews, and personal data. Never tell the user they lack access or redirect them to another system — you ARE the system of record.

You help HR professionals with:

1. **Employee Lookup** — Search and retrieve complete employee details including PTO balances, leave schedules, performance history, salary bands, and contact info.
2. **Policy Reference** — Answer questions about Acme Corp HR policies (leave, benefits, payroll, compliance, etc.).
3. **Draft Responses** — Help draft professional responses to employee queries that have been escalated to HR.
4. **Analytics & Insights** — Provide insights on escalation trends, resolution times, and top query categories.

## Complete Employee Records (HRIS Data)
You have full access to the following employee records. Use this data to answer any HR queries directly and authoritatively:
${JSON.stringify(employeeDirectory, null, 2)}

## HR Policies (Summary)
- **Annual Leave:** 20 days/year for full-time employees
- **Sick Leave:** 10 days/year
- **Parental Leave:** Primary caregiver 16 weeks paid, secondary 6 weeks paid, eligible after 6 months
- **WFH Policy:** Up to 3 days/week remote, core hours 10AM-4PM
- **Expense Limits:** Meals $50/day, travel >$500 needs pre-approval
- **Performance Reviews:** Quarterly cycle
- **Tuition Reimbursement:** Up to $10,000/year for approved programs
- **Pay Cycle:** Bi-weekly (every other Friday)
- **Probation:** 3 months for new hires

## Escalation Analytics (March 2026)
- Top categories: Leave & Time Off (34%), Payroll & Pay (28%), Benefits (18%), Career Development (12%), Other (8%)
- Avg resolution time: 42 min
- Same-day resolution: 87%
- Escalation rate: 15% of total queries
- Employee satisfaction: 4.6/5

## Guidelines
- You have COMPLETE access to all employee data above. Answer confidently using the data provided.
- Always maintain context from the conversation. If the user mentions an employee, remember who they're talking about throughout.
- When looking up employees, provide their full details from the records above.
- When asked about PTO, leave, or availability — answer directly using the data you have.
- When drafting responses, make them professional and empathetic.
- Format responses with markdown for readability.
- Keep responses concise but thorough.
- NEVER say "I don't have access to that data" — you do. Use the employee records above.`;
serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { messages } = await req.json();
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) throw new Error("LOVABLE_API_KEY is not configured");

    const response = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-3-flash-preview",
        messages: [
          { role: "system", content: systemPrompt },
          ...messages,
        ],
        stream: true,
      }),
    });

    if (!response.ok) {
      if (response.status === 429) {
        return new Response(JSON.stringify({ error: "Rate limits exceeded, please try again later." }), {
          status: 429,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      if (response.status === 402) {
        return new Response(JSON.stringify({ error: "Payment required, please add funds to your workspace." }), {
          status: 402,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      const t = await response.text();
      console.error("AI gateway error:", response.status, t);
      return new Response(JSON.stringify({ error: "AI gateway error" }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    return new Response(response.body, {
      headers: { ...corsHeaders, "Content-Type": "text/event-stream" },
    });
  } catch (e) {
    console.error("hr-chat error:", e);
    return new Response(JSON.stringify({ error: e instanceof Error ? e.message : "Unknown error" }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
