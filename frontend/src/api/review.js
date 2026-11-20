import{api}from'./client.js';
export const reviewCustomer=customer=>api('/review/customers/'+encodeURIComponent(customer));
