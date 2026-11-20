export const routes=[['payments','01','到账款'],['bills','02','账单'],['claims','03','认领办理'],['review','04','复核视图']];export const current=()=>location.hash.slice(1).split('/')[0]||'payments';
