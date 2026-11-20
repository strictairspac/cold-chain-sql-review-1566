/** @typedef {{id:number,payment_no:string,customer:string,received_amount:string,balance:string,status:string,created_at:string}} Payment */
/** @typedef {{id:number,bill_no:string,customer:string,amount:string,outstanding:string,status:string,created_at:string}} Bill */
/** @typedef {{id:number,idempotency_key:string,payment_no:string,bill_no:string,customer:string,amount:string,status:string,reject_reason:?string,receipt_no:?string,created_by:string,created_at:string,posted_at:?string}} Claim */
/** @typedef {{receipt_no:string,claim_id:number,payment_no:string,bill_no:string,customer:string,amount:string,payment_balance_after:string,bill_outstanding_after:string,posted_at:string,operator:string}} Receipt */
/** @typedef {{customer:string,payments:Payment[],bills:Bill[],allocations:Object[],checks:Object[],totals:Object,reconciled:boolean,snapshot:string}} ReviewSnapshot */
export const entityNames={payment:'到账款',bill:'账单',claim:'认领单',receipt:'回执',reversal:'冲回'};
