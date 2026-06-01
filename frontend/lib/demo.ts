// ── Self-contained demo dataset ────────────────────────────────────────────────
// Powers the whole app when the backend endpoints aren't live (see
// memory: deployed-backend-gap). All timestamps are fixed absolute values so
// server and client render identically (no hydration drift). "Today" in the
// scenario is 2026-05-31, so files before ~2023-05 are past the 3-year window.

import { articlesFor } from "./gdpr";
import type {
  Detector,
  Finding,
  PiiCategory,
  ScanRun,
  ScannedFile,
  SourceType,
  User,
} from "./types";

const D = (iso: string): number => new Date(`${iso}T10:00:00Z`).getTime();
const SCANNED_AT = D("2026-05-20");

// ── Users ───────────────────────────────────────────────────────────────────
export const DEMO_USERS: User[] = [
  { id: "steward_comp", name: "Amara Okafor", email: "amara.okafor@bosch.example", role: "employee", department: "Procurement" },
  { id: "lena_hoffmann", name: "Lena Hoffmann", email: "lena.hoffmann@bosch.example", role: "employee", department: "Human Resources" },
  { id: "marco_bianchi", name: "Marco Bianchi", email: "marco.bianchi@bosch.example", role: "employee", department: "Finance" },
  { id: "priya_nair", name: "Priya Nair", email: "priya.nair@bosch.example", role: "employee", department: "Facilities" },
  { id: "jonas_keller", name: "Jonas Keller", email: "jonas.keller@bosch.example", role: "employee", department: "Sales DACH" },
  { id: "emp_clean", name: "Tom Richter", email: "tom.richter@bosch.example", role: "employee", department: "IT Operations" },
  { id: "admin_dpo", name: "Klaus Weber", email: "klaus.weber@bosch.example", role: "admin", department: "Data Protection Office" },
];

/** Credentials → user id. (admin/admin) and (user/user) per FRONTEND.md. */
export const CREDENTIALS: Record<string, { password: string; userId: string }> = {
  admin: { password: "admin", userId: "admin_dpo" },
  user: { password: "user", userId: "steward_comp" },
};

export const DEFAULT_EMPLOYEE_ID = "steward_comp";
export const ADMIN_ID = "admin_dpo";

// ── File spec → ScannedFile builder ───────────────────────────────────────────
interface FindingSpec {
  category: PiiCategory;
  snippet: string;
  confidence: number;
  detector: Detector;
}
interface FileSpec {
  name: string;
  source: SourceType;
  owner: string;
  master?: string | null;
  modified: number;
  size: number;
  text: string;
  findings: FindingSpec[];
}

const SOURCE_ROOT: Record<SourceType, string> = {
  onedrive: "OneDrive/Documents",
  sharepoint: "SharePoint/Sites",
  fileshare: "\\\\fileshare01\\dept",
  gdrive: "GoogleDrive/My Drive",
};

const MIME: Record<string, string> = {
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  csv: "text/csv",
  txt: "text/plain",
  md: "text/markdown",
};
const mimeFor = (name: string) => MIME[name.split(".").pop() ?? ""] ?? "application/octet-stream";

function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function buildFile(spec: FileSpec): ScannedFile {
  const id = slug(`${spec.owner}-${spec.name}`);
  const findings: Finding[] = spec.findings.map((f, i) => ({
    id: `${id}-f${i}`,
    fileId: id,
    category: f.category,
    snippet: f.snippet,
    confidence: f.confidence,
    detector: f.detector,
    gdprArticles: articlesFor(f.category),
  }));
  return {
    id,
    name: spec.name,
    path: `${SOURCE_ROOT[spec.source]}/${spec.name}`,
    sourceType: spec.source,
    mimeType: mimeFor(spec.name),
    sizeBytes: spec.size,
    lastModified: spec.modified,
    lastScannedAt: SCANNED_AT,
    ownerUserId: spec.owner,
    masterUserId: spec.master ?? null,
    text: spec.text.trim(),
    findings,
  };
}

// ── Flagged files (have findings) ─────────────────────────────────────────────
const FLAGGED: FileSpec[] = [
  {
    name: "Supplier_Onboarding_Example_A.pdf",
    source: "fileshare",
    owner: "steward_comp",
    modified: D("2021-03-12"),
    size: 248_400,
    text: `SUPPLIER ONBOARDING FORM — Robert Bosch GmbH, Procurement
Company: Nordwind Logistik GmbH
Primary contact: Markus Bergmann
Email: m.bergmann@nordwind-logistik.de
Phone: +49 711 4023 8890
Registered address: Industriestraße 14, 70565 Stuttgart, Germany
VAT / Tax ID: DE 815 932 047
Authorised signatory: Markus Bergmann (signed and dated 12.03.2021)
Remit-to / billing address: Postfach 90 12 33, 70565 Stuttgart`,
    findings: [
      { category: "name", snippet: "Primary contact: Markus Bergmann", confidence: 0.88, detector: "ner" },
      { category: "email", snippet: "m.bergmann@nordwind-logistik.de", confidence: 0.99, detector: "regex" },
      { category: "phone", snippet: "+49 711 4023 8890", confidence: 0.97, detector: "regex" },
      { category: "home_address", snippet: "Industriestraße 14, 70565 Stuttgart, Germany", confidence: 0.82, detector: "ner" },
      { category: "id_card", snippet: "VAT / Tax ID: DE 815 932 047", confidence: 0.94, detector: "regex" },
      { category: "signature", snippet: "Authorised signatory: Markus Bergmann (signed and dated 12.03.2021)", confidence: 0.71, detector: "llm" },
      { category: "billing_shipping_address", snippet: "Remit-to / billing address: Postfach 90 12 33, 70565 Stuttgart", confidence: 0.79, detector: "ner" },
    ],
  },
  {
    name: "Supplier_Onboarding.pdf",
    source: "sharepoint",
    owner: "steward_comp",
    master: "steward_comp",
    modified: D("2025-11-04"),
    size: 192_800,
    text: `SUPPLIER MASTER RECORD
Vendor: Helvetia Precision AG
Account manager: Sofia Lindqvist
Email: sofia.lindqvist@helvetia-precision.ch
Phone: +41 44 668 21 09
Shipping address: Bahnhofstrasse 22, 8001 Zürich, Switzerland`,
    findings: [
      { category: "name", snippet: "Account manager: Sofia Lindqvist", confidence: 0.86, detector: "ner" },
      { category: "email", snippet: "sofia.lindqvist@helvetia-precision.ch", confidence: 0.99, detector: "regex" },
      { category: "phone", snippet: "+41 44 668 21 09", confidence: 0.96, detector: "regex" },
      { category: "billing_shipping_address", snippet: "Shipping address: Bahnhofstrasse 22, 8001 Zürich", confidence: 0.8, detector: "ner" },
    ],
  },
  {
    name: "Expense_Report_Example_A.pdf",
    source: "fileshare",
    owner: "steward_comp",
    modified: D("2021-08-19"),
    size: 161_200,
    text: `TRAVEL EXPENSE REPORT — Q3 2021
Employee: Amara Okafor
Reimburse to: amara.okafor@bosch.example
Trip: Stuttgart → Munich → Vienna (rail + air), 04–09 Aug 2021
Hotel billing address: Kärntner Ring 9, 1010 Vienna, Austria
Itinerary ref: LH1234 / OS0231, seat 14C`,
    findings: [
      { category: "name", snippet: "Employee: Amara Okafor", confidence: 0.9, detector: "ner" },
      { category: "email", snippet: "amara.okafor@bosch.example", confidence: 0.99, detector: "regex" },
      { category: "travel_history", snippet: "Stuttgart → Munich → Vienna (rail + air), 04–09 Aug 2021", confidence: 0.68, detector: "llm" },
      { category: "billing_shipping_address", snippet: "Hotel billing address: Kärntner Ring 9, 1010 Vienna", confidence: 0.77, detector: "ner" },
    ],
  },
  {
    name: "Expense_Report.pdf",
    source: "onedrive",
    owner: "steward_comp",
    modified: D("2026-02-10"),
    size: 178_500,
    text: `TRAVEL EXPENSE REPORT — Feb 2026
Employee: Amara Okafor (amara.okafor@bosch.example)
Trip: Stuttgart → Lyon → Stuttgart, 03–05 Feb 2026
Billing address for hotel: 12 Rue de la République, 69002 Lyon, France`,
    findings: [
      { category: "name", snippet: "Employee: Amara Okafor", confidence: 0.91, detector: "ner" },
      { category: "email", snippet: "amara.okafor@bosch.example", confidence: 0.99, detector: "regex" },
      { category: "travel_history", snippet: "Stuttgart → Lyon → Stuttgart, 03–05 Feb 2026", confidence: 0.66, detector: "llm" },
      { category: "billing_shipping_address", snippet: "12 Rue de la République, 69002 Lyon, France", confidence: 0.76, detector: "ner" },
    ],
  },
  {
    name: "Incident_Report_Example_B.pdf",
    source: "sharepoint",
    owner: "steward_comp",
    master: "steward_comp",
    modified: D("2026-01-22"),
    size: 203_900,
    text: `SECURITY INCIDENT REPORT #INC-2026-0142
Reported by: Amara Okafor
Contact: +49 711 811 0
Witness: Daniel Fischer (daniel.fischer@bosch.example)
Evidence: CCTV still attached (gate-camera-3.jpg) showing the individual involved.`,
    findings: [
      { category: "name", snippet: "Witness: Daniel Fischer", confidence: 0.87, detector: "ner" },
      { category: "email", snippet: "daniel.fischer@bosch.example", confidence: 0.99, detector: "regex" },
      { category: "phone", snippet: "+49 711 811 0", confidence: 0.93, detector: "regex" },
      { category: "photo_video", snippet: "CCTV still attached (gate-camera-3.jpg) showing the individual", confidence: 0.64, detector: "llm" },
    ],
  },
  {
    name: "IT_Access_Request_Example_B.pdf",
    source: "fileshare",
    owner: "steward_comp",
    modified: D("2022-02-15"),
    size: 142_300,
    text: `IT ACCESS REQUEST FORM
Requested for: Amara Okafor
Login / username: a.okafor
Corporate email: amara.okafor@bosch.example
Employee ID: E-20491
System: SAP Ariba (Procurement role)`,
    findings: [
      { category: "name", snippet: "Requested for: Amara Okafor", confidence: 0.9, detector: "ner" },
      { category: "username", snippet: "Login / username: a.okafor", confidence: 0.95, detector: "regex" },
      { category: "email", snippet: "amara.okafor@bosch.example", confidence: 0.99, detector: "regex" },
      { category: "id_card", snippet: "Employee ID: E-20491", confidence: 0.9, detector: "regex" },
    ],
  },
  {
    name: "Training_Evaluation_Example_A.pdf",
    source: "onedrive",
    owner: "lena_hoffmann",
    modified: D("2025-09-30"),
    size: 221_700,
    text: `TRAINING EVALUATION — GDPR Awareness 2025
Participant: Carlos Mendez
Email: carlos.mendez@bosch.example
Trainer sign-off: Lena Hoffmann (signature on file)
Photo consent: participant headshot stored for the certificate (mendez_cert.png).`,
    findings: [
      { category: "name", snippet: "Participant: Carlos Mendez", confidence: 0.89, detector: "ner" },
      { category: "email", snippet: "carlos.mendez@bosch.example", confidence: 0.99, detector: "regex" },
      { category: "signature", snippet: "Trainer sign-off: Lena Hoffmann (signature on file)", confidence: 0.69, detector: "llm" },
      { category: "photo_video", snippet: "participant headshot stored for the certificate (mendez_cert.png)", confidence: 0.62, detector: "llm" },
    ],
  },
  {
    name: "Training_Evaluation.pdf",
    source: "sharepoint",
    owner: "lena_hoffmann",
    master: "lena_hoffmann",
    modified: D("2026-03-15"),
    size: 188_100,
    text: `TRAINING EVALUATION — Leadership Program
Participant: Nadia Al-Rashid
Email: nadia.alrashid@bosch.example
Phone: +49 151 2233 4455
Overall rating: 4.6 / 5`,
    findings: [
      { category: "name", snippet: "Participant: Nadia Al-Rashid", confidence: 0.88, detector: "ner" },
      { category: "email", snippet: "nadia.alrashid@bosch.example", confidence: 0.99, detector: "regex" },
      { category: "phone", snippet: "+49 151 2233 4455", confidence: 0.96, detector: "regex" },
    ],
  },
  {
    name: "Passport_Copy_Onboarding.pdf",
    source: "fileshare",
    owner: "lena_hoffmann",
    modified: D("2022-06-01"),
    size: 1_842_000,
    text: `NEW HIRE ONBOARDING — Identity Verification
Name: Yuki Tanaka
Passport number: C01X00T47
Home address: Lindenstraße 8, 10969 Berlin, Germany
Attached: scanned passport photo page (tanaka_passport.jpg)
Signature: Y. Tanaka`,
    findings: [
      { category: "name", snippet: "Name: Yuki Tanaka", confidence: 0.9, detector: "ner" },
      { category: "passport", snippet: "Passport number: C01X00T47", confidence: 0.97, detector: "regex" },
      { category: "home_address", snippet: "Lindenstraße 8, 10969 Berlin, Germany", confidence: 0.83, detector: "ner" },
      { category: "photo_video", snippet: "scanned passport photo page (tanaka_passport.jpg)", confidence: 0.6, detector: "llm" },
      { category: "signature", snippet: "Signature: Y. Tanaka", confidence: 0.67, detector: "llm" },
    ],
  },
  {
    name: "New_Hire_Forms_2023.docx",
    source: "onedrive",
    owner: "lena_hoffmann",
    modified: D("2023-01-10"),
    size: 96_400,
    text: `NEW HIRE FORM
Name: Felix Braun
Home address: Goethestraße 31, 60313 Frankfurt am Main
Personal mobile: +49 160 9988 776
Email: felix.braun@bosch.example
National ID card no.: L01XY2Z34`,
    findings: [
      { category: "name", snippet: "Name: Felix Braun", confidence: 0.9, detector: "ner" },
      { category: "home_address", snippet: "Goethestraße 31, 60313 Frankfurt am Main", confidence: 0.84, detector: "ner" },
      { category: "phone", snippet: "+49 160 9988 776", confidence: 0.96, detector: "regex" },
      { category: "email", snippet: "felix.braun@bosch.example", confidence: 0.99, detector: "regex" },
      { category: "id_card", snippet: "National ID card no.: L01XY2Z34", confidence: 0.92, detector: "regex" },
    ],
  },
  {
    name: "Expense_Report_Example_B.pdf",
    source: "onedrive",
    owner: "marco_bianchi",
    modified: D("2026-04-02"),
    size: 175_300,
    text: `TRAVEL EXPENSE REPORT — Mar 2026
Employee: Marco Bianchi (marco.bianchi@bosch.example)
Trip: Milan → Frankfurt → Milan, 18–20 Mar 2026
Hotel billing: Via Tortona 35, 20144 Milano, Italy`,
    findings: [
      { category: "name", snippet: "Employee: Marco Bianchi", confidence: 0.91, detector: "ner" },
      { category: "email", snippet: "marco.bianchi@bosch.example", confidence: 0.99, detector: "regex" },
      { category: "billing_shipping_address", snippet: "Hotel billing: Via Tortona 35, 20144 Milano, Italy", confidence: 0.78, detector: "ner" },
      { category: "travel_history", snippet: "Milan → Frankfurt → Milan, 18–20 Mar 2026", confidence: 0.65, detector: "llm" },
    ],
  },
  {
    name: "Vendor_Invoices_Q1.xlsx",
    source: "sharepoint",
    owner: "marco_bianchi",
    master: "marco_bianchi",
    modified: D("2026-03-28"),
    size: 512_800,
    text: `VENDOR INVOICES — Q1 2026 (extract)
Contact: Elena Petrova | elena.petrova@meridian-parts.eu | +49 89 5500 1212
Bill-to: Meridian Parts GmbH, Leopoldstraße 200, 80804 München
Contact: Hans Gruber | h.gruber@meridian-parts.eu | +49 89 5500 1213`,
    findings: [
      { category: "name", snippet: "Contact: Elena Petrova", confidence: 0.85, detector: "ner" },
      { category: "email", snippet: "elena.petrova@meridian-parts.eu", confidence: 0.99, detector: "regex" },
      { category: "phone", snippet: "+49 89 5500 1212", confidence: 0.95, detector: "regex" },
      { category: "billing_shipping_address", snippet: "Leopoldstraße 200, 80804 München", confidence: 0.79, detector: "ner" },
    ],
  },
  {
    name: "Corporate_Card_Holders.csv",
    source: "fileshare",
    owner: "marco_bianchi",
    modified: D("2024-12-05"),
    size: 84_900,
    text: `name,email,billing_city,cost_center
Marco Bianchi,marco.bianchi@bosch.example,Stuttgart,CC-4471
Sofia Lindqvist,sofia.lindqvist@bosch.example,Zürich,CC-4480
Jonas Keller,jonas.keller@bosch.example,Hamburg,CC-4491`,
    findings: [
      { category: "name", snippet: "Marco Bianchi, Sofia Lindqvist, Jonas Keller (3 rows)", confidence: 0.84, detector: "ner" },
      { category: "email", snippet: "marco.bianchi@bosch.example (+2 more)", confidence: 0.99, detector: "regex" },
      { category: "billing_shipping_address", snippet: "billing_city: Stuttgart, Zürich, Hamburg", confidence: 0.72, detector: "llm" },
    ],
  },
  {
    name: "Visitor_Log_March.xlsx",
    source: "sharepoint",
    owner: "priya_nair",
    master: "priya_nair",
    modified: D("2026-03-31"),
    size: 333_200,
    text: `VISITOR LOG — Reception, March 2026
Visitor: Dr. Anke Vogel | anke.vogel@externe-beratung.de | +49 30 1234 5678
Badge photo captured at check-in (visitor_8841.jpg)
Visitor: Tomáš Novák | t.novak@supplier.cz`,
    findings: [
      { category: "name", snippet: "Visitor: Dr. Anke Vogel", confidence: 0.86, detector: "ner" },
      { category: "email", snippet: "anke.vogel@externe-beratung.de", confidence: 0.99, detector: "regex" },
      { category: "phone", snippet: "+49 30 1234 5678", confidence: 0.95, detector: "regex" },
      { category: "photo_video", snippet: "Badge photo captured at check-in (visitor_8841.jpg)", confidence: 0.63, detector: "llm" },
    ],
  },
  {
    name: "Driver_Pool_Bookings.csv",
    source: "fileshare",
    owner: "priya_nair",
    modified: D("2025-07-12"),
    size: 67_500,
    text: `POOL CAR BOOKINGS
Driver: Priya Nair
Driver's licence no.: B072RRE2I55
Mobile: +49 172 4567 890
Route: Renningen → Stuttgart Airport → Renningen`,
    findings: [
      { category: "name", snippet: "Driver: Priya Nair", confidence: 0.9, detector: "ner" },
      { category: "drivers_license", snippet: "Driver's licence no.: B072RRE2I55", confidence: 0.93, detector: "regex" },
      { category: "phone", snippet: "+49 172 4567 890", confidence: 0.96, detector: "regex" },
      { category: "travel_history", snippet: "Renningen → Stuttgart Airport → Renningen", confidence: 0.61, detector: "llm" },
    ],
  },
  {
    name: "Incident_Report_Example_A.pdf",
    source: "onedrive",
    owner: "priya_nair",
    modified: D("2026-02-28"),
    size: 198_600,
    text: `FACILITIES INCIDENT REPORT #FAC-2026-0098
Affected employee: Ingrid Sørensen
Home address on file: Storgata 5, 0155 Oslo, Norway
Phone: +47 22 33 44 55
Photo of damaged equipment attached (locker_row_b.jpg)`,
    findings: [
      { category: "name", snippet: "Affected employee: Ingrid Sørensen", confidence: 0.87, detector: "ner" },
      { category: "home_address", snippet: "Storgata 5, 0155 Oslo, Norway", confidence: 0.81, detector: "ner" },
      { category: "phone", snippet: "+47 22 33 44 55", confidence: 0.94, detector: "regex" },
      { category: "photo_video", snippet: "Photo of damaged equipment attached (locker_row_b.jpg)", confidence: 0.58, detector: "llm" },
    ],
  },
  {
    name: "IT_Access_Request_Example_A.pdf",
    source: "onedrive",
    owner: "jonas_keller",
    modified: D("2026-04-20"),
    size: 138_900,
    text: `IT ACCESS REQUEST FORM
Requested for: Jonas Keller
Login / username: j.keller
Corporate email: jonas.keller@bosch.example
System: Salesforce (Sales DACH role)`,
    findings: [
      { category: "name", snippet: "Requested for: Jonas Keller", confidence: 0.9, detector: "ner" },
      { category: "username", snippet: "Login / username: j.keller", confidence: 0.95, detector: "regex" },
      { category: "email", snippet: "jonas.keller@bosch.example", confidence: 0.99, detector: "regex" },
    ],
  },
  {
    name: "Customer_Contacts_DACH.xlsx",
    source: "sharepoint",
    owner: "jonas_keller",
    master: "jonas_keller",
    modified: D("2026-05-02"),
    size: 742_100,
    text: `CUSTOMER CONTACTS — DACH (extract)
Birgit Schäfer | b.schaefer@kunde-dach.de | tel +49 221 9000 100 | fax +49 221 9000 199
Delivery address: Hohenzollernring 72, 50672 Köln
Lukas Wagner | l.wagner@kunde-dach.de | tel +43 1 9000 200`,
    findings: [
      { category: "name", snippet: "Birgit Schäfer", confidence: 0.85, detector: "ner" },
      { category: "email", snippet: "b.schaefer@kunde-dach.de (+1 more)", confidence: 0.99, detector: "regex" },
      { category: "phone", snippet: "tel +49 221 9000 100", confidence: 0.95, detector: "regex" },
      { category: "fax", snippet: "fax +49 221 9000 199", confidence: 0.9, detector: "regex" },
      { category: "billing_shipping_address", snippet: "Hohenzollernring 72, 50672 Köln", confidence: 0.78, detector: "ner" },
    ],
  },
];

// ── Clean files (processed, no findings) — make KPIs / source mix realistic ────
const CLEAN: Array<{ name: string; source: SourceType; owner: string; master?: string | null; modified: number; size: number }> = [
  { name: "Quarterly_Strategy_Review.pptx", source: "sharepoint", owner: "admin_dpo", master: null, modified: D("2026-05-12"), size: 4_210_000 },
  { name: "Product_Roadmap_2026.pdf", source: "onedrive", owner: "jonas_keller", modified: D("2026-04-28"), size: 1_120_000 },
  { name: "Budget_Template.xlsx", source: "sharepoint", owner: "marco_bianchi", master: "marco_bianchi", modified: D("2026-03-02"), size: 88_000 },
  { name: "Release_Checklist.md", source: "fileshare", owner: "emp_clean", modified: D("2026-05-18"), size: 12_400 },
  { name: "Team_Offsite_Agenda.pdf", source: "onedrive", owner: "emp_clean", modified: D("2026-05-09"), size: 320_000 },
  { name: "Architecture_Overview.pdf", source: "sharepoint", owner: "emp_clean", master: null, modified: D("2026-04-15"), size: 2_050_000 },
  { name: "Server_Inventory.csv", source: "fileshare", owner: "emp_clean", modified: D("2026-05-21"), size: 45_300 },
  { name: "Meeting_Notes_Weekly.docx", source: "onedrive", owner: "priya_nair", modified: D("2026-05-19"), size: 54_800 },
  { name: "Compliance_Policy_v4.pdf", source: "sharepoint", owner: "admin_dpo", master: null, modified: D("2026-02-20"), size: 690_000 },
  { name: "Marketing_Brand_Guide.pdf", source: "onedrive", owner: "jonas_keller", modified: D("2026-01-30"), size: 8_400_000 },
  { name: "Sprint_Retro_Board.png", source: "fileshare", owner: "emp_clean", modified: D("2026-05-22"), size: 980_000 },
  { name: "Open_Source_Licenses.txt", source: "fileshare", owner: "emp_clean", modified: D("2026-04-01"), size: 33_900 },
];

export const DEMO_FILES: ScannedFile[] = [
  ...FLAGGED.map(buildFile),
  ...CLEAN.map((c) =>
    buildFile({
      ...c,
      master: c.master ?? null,
      text: `Internal working document. No personal data detected by the scanner.`,
      findings: [],
    })
  ),
];

// ── Past scan snapshots (admin history) ────────────────────────────────────────
export const DEMO_SCAN_RUNS: ScanRun[] = [
  {
    id: "run-2026-05-20",
    label: "full:2026-05-20",
    type: "full",
    startedAt: D("2026-05-20"),
    finishedAt: D("2026-05-20") + 142_000,
    durationSec: 142,
    filesScanned: 30,
    filesFlagged: 18,
    filesNotFlagged: 12,
    bytesScanned: DEMO_FILES.reduce((a, f) => a + f.sizeBytes, 0),
    totalFindings: FLAGGED.reduce((a, f) => a + f.findings.length, 0),
    pending: 18,
    deleted: 0,
    cancelled: 0,
    extended: 0,
  },
  {
    id: "run-2026-04-15",
    label: "full:2026-04-15",
    type: "full",
    startedAt: D("2026-04-15"),
    finishedAt: D("2026-04-15") + 138_000,
    durationSec: 138,
    filesScanned: 28,
    filesFlagged: 17,
    filesNotFlagged: 11,
    bytesScanned: 22_400_000,
    totalFindings: 61,
    pending: 6,
    deleted: 7,
    cancelled: 3,
    extended: 1,
  },
  {
    id: "run-2026-03-15",
    label: "delta:2026-03-15",
    type: "delta",
    startedAt: D("2026-03-15"),
    finishedAt: D("2026-03-15") + 41_000,
    durationSec: 41,
    filesScanned: 9,
    filesFlagged: 6,
    filesNotFlagged: 3,
    bytesScanned: 6_900_000,
    totalFindings: 24,
    pending: 9,
    deleted: 4,
    cancelled: 2,
    extended: 2,
  },
  {
    id: "run-2026-02-15",
    label: "delta:2026-02-15",
    type: "delta",
    startedAt: D("2026-02-15"),
    finishedAt: D("2026-02-15") + 38_000,
    durationSec: 38,
    filesScanned: 7,
    filesFlagged: 5,
    filesNotFlagged: 2,
    bytesScanned: 5_100_000,
    totalFindings: 19,
    pending: 11,
    deleted: 2,
    cancelled: 1,
    extended: 1,
  },
  {
    id: "run-2026-01-15",
    label: "full:2026-01-15",
    type: "full",
    startedAt: D("2026-01-15"),
    finishedAt: D("2026-01-15") + 129_000,
    durationSec: 129,
    filesScanned: 25,
    filesFlagged: 14,
    filesNotFlagged: 11,
    bytesScanned: 19_800_000,
    totalFindings: 48,
    pending: 14,
    deleted: 0,
    cancelled: 0,
    extended: 0,
  },
];
