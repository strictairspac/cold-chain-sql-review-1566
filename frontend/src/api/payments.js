import{api,post}from'./client.js';
export const listPayments=(params={})=>api('/payments'+query(params));
export const createPayment=data=>post('/payments',data);
export const reversePayment=(id,reason)=>post('/payments/'+id+'/reverse',{reason});
export const listCustomers=()=>api('/payments/meta/customers');
const query=o=>{const q=new URLSearchParams(Object.entries(o).filter(([,v])=>v));const s=q.toString();return s?'?'+s:''};
