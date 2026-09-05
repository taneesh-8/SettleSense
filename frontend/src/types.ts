export interface Order {
  order_id: string;
  created_at: string;
  customer: string;
  amount_paise: number;
  refund_paise: number;
  payment_method: string;
  status: string;
  tag: string;
}

export interface Settlement {
  settlement_id: string;
  order_id: string;
  utr: string;
  settled_at: string;
  gross_paise: number;
  fee_paise: number;
  gst_paise: number;
  tds_paise: number;
  net_paise: number;
  tag: string;
}

export interface BankCredit {
  utr: string;
  credited_at: string;
  amount_paise: number;
  description: string;
  tag: string;
}

export interface ConfirmedMatch {
  match_id: string;
  order_ids: string[];
  settlement_ids: string[];
  utr: string;
  bank_utr: string;
  gross_paise: number;
  net_paise: number;
  bank_paise: number;
  stage: string;
  method: string;
  reason: string;
}

export interface ExceptionItem {
  exception_id: string;
  record_type: string;
  record_id: string;
  level: string;
  stage: string;
  reason: string;
  amount_paise: number;
  risk_flag: boolean;
  tag: string;
  order_ids: string[];
}

export interface AuditEntry {
  seq: number;
  stage: string;
  action: string;
  record_id: string;
  detail: string;
  ai_used: boolean;
}

export interface ReconciliationReport {
  total_orders: number;
  total_settlements: number;
  total_bank_credits: number;
  confirmed_count: number;
  confirmed_order_count: number;
  exception_count: number;
  match_rate: number;
  rupees_reconciled: number;
  rupees_at_risk: number;
  rupees_flagged_total: number;
  paise_reconciled: number;
  paise_at_risk: number;
  paise_flagged_total: number;
  stage_counts: Record<string, number>;
  fuzzy_mode: string;
}


export interface ReconciliationResult {
  report: ReconciliationReport;
  confirmed: ConfirmedMatch[];
  exceptions: ExceptionItem[];
  audit_log: AuditEntry[];
  orders: Order[];
  settlements: Settlement[];
  bank: BankCredit[];
}

export interface GeneratedBatch {
  seed: number;
  orders: any[];
  settlements: any[];
  bank: any[];
  counts: {
    orders: number;
    settlements: number;
    bank: number;
  };
}
