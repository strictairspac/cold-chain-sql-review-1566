import{CLAIM_STATUS}from'../../constants/enums.js';import{esc}from'../../utils/html.js';export const badge=(s,labels=CLAIM_STATUS)=>'<span class="badge '+esc(s)+'">'+esc(labels[s]||s)+'</span>';
