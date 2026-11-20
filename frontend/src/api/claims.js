import{api,post}from'./client.js';
export const listClaims=(params={})=>api('/claims'+query(params));
export const createClaim=data=>post('/claims',data);
export const processClaim=id=>post('/claims/'+id+'/process');
export const fetchReceipt=id=>api('/claims/'+id+'/receipt');
const query=o=>{const q=new URLSearchParams(Object.entries(o).filter(([,v])=>v));const s=q.toString();return s?'?'+s:''};
