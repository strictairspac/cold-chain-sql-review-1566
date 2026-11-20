import{api,post}from'./client.js';
export const listBills=(params={})=>api('/bills'+query(params));
export const createBill=data=>post('/bills',data);
const query=o=>{const q=new URLSearchParams(Object.entries(o).filter(([,v])=>v));const s=q.toString();return s?'?'+s:''};
