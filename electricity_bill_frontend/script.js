const API = "http://127.0.0.1:5000/api";
const $ = id => document.getElementById(id);
let cache = {consumers:[], connections:[], usage:[], bills:[], slabs:[]};

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function money(value) {
  return "₹" + Number(value || 0).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2});
}
function notify(message, error=false) {
  const el=$("message"); el.textContent=message; el.style.background=error?"#9f2d36":"#1d2b42";
  el.classList.add("show"); window.clearTimeout(notify.timer); notify.timer=window.setTimeout(()=>el.classList.remove("show"),5000);
}
async function api(path, options={}) {
  const response=await fetch(API+path,{...options,headers:{"Content-Type":"application/json",...(options.headers||{})}});
  const body=await response.json().catch(()=>({error:"Invalid response from server"}));
  if(!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}
function fillSelect(id, items, valueKey, labelFn, placeholder) {
  const select=$(id), previous=select.value;
  select.innerHTML=`<option value="">${esc(placeholder)}</option>`+items.map(x=>`<option value="${esc(x[valueKey])}">${esc(labelFn(x))}</option>`).join("");
  if(items.some(x=>String(x[valueKey])===previous)) select.value=previous;
}
function render() {
  $("stat-consumers").textContent=cache.consumers.length;
  $("stat-connections").textContent=cache.connections.filter(x=>x.Status==="Active").length;
  $("stat-bills").textContent=cache.bills.length;
  $("stat-pending").textContent=cache.bills.filter(x=>x.Payment_Status!=="Paid").length;

  $("consumers").innerHTML=cache.consumers.map(x=>`<tr><td>${x.Consumer_ID}</td><td>${esc(x.Name)}</td><td>${esc(x.Phone)}</td><td>${esc(x.Email)}</td><td>${esc(x.Address||"—")}</td></tr>`).join("")||'<tr><td colspan="5">No consumers yet.</td></tr>';
  $("connections").innerHTML=cache.connections.map(x=>`<tr><td>${x.Connection_ID}</td><td>${esc(x.Consumer_Name)}</td><td>${esc(x.Connection_Type)}</td><td>${esc(x.Meter_No)}</td><td>${esc(x.Status)}</td></tr>`).join("")||'<tr><td colspan="5">No connections yet.</td></tr>';
  $("usage").innerHTML=cache.usage.map(x=>`<tr><td>${x.Record_ID}</td><td>${esc(x.Consumer_Name)}</td><td>${esc(x.Meter_No)}</td><td>${esc(x.Read_Date)}</td><td>${Number(x.Units_Consumed).toFixed(2)}</td></tr>`).join("")||'<tr><td colspan="5">No usage records yet.</td></tr>';
  $("bills").innerHTML=cache.bills.map(x=>`<tr><td>${x.Bill_ID}</td><td>${esc(x.Consumer_Name)}</td><td>${Number(x.Units_Consumed).toFixed(2)}</td><td>${money(x.Energy_Charge)}</td><td>${money(x.Subsidy)}</td><td><strong>${money(x.Final_Amount)}</strong></td><td>${esc(x.Due_Date)}</td><td>${esc(x.Payment_Status)}</td><td>${x.Payment_Status==="Paid"?"—":`<button class="pay-btn" data-paid="${x.Bill_ID}">Mark paid</button>`}</td></tr>`).join("")||'<tr><td colspan="9">No bills yet.</td></tr>';
  $("slabs").innerHTML=cache.slabs.map(x=>`<tr><td>${x.Breakdown_ID}</td><td>${x.Bill_ID}</td><td>${esc(x.Slab_Range)}</td><td>${Number(x.Units_In_Slab).toFixed(2)}</td><td>${money(x.Rate)}</td><td>${money(x.Slab_Amount)}</td></tr>`).join("")||'<tr><td colspan="6">No slab breakdowns yet.</td></tr>';

  fillSelect("connection-consumer",cache.consumers,"Consumer_ID",x=>`${x.Consumer_ID} — ${x.Name}`,"Choose consumer");
  fillSelect("usage-connection",cache.connections.filter(x=>x.Status==="Active"),"Connection_ID",x=>`${x.Connection_ID} — ${x.Consumer_Name} (${x.Meter_No})`,"Choose active connection");
  const billedIds=new Set(cache.bills.map(x=>String(x.Record_ID)));
  fillSelect("bill-record",cache.usage.filter(x=>!billedIds.has(String(x.Record_ID))),"Record_ID",x=>`${x.Record_ID} — ${x.Consumer_Name}, ${x.Units_Consumed} units`,"Choose unbilled usage record");
}
async function refresh() {
  try {
    const health=await api("/health");
    $("api-status").textContent=health.database==="connected"?"MySQL connected":"Database unavailable";
    const [consumers,connections,usage,bills,slabs]=await Promise.all([
      api("/consumers"),api("/connections"),api("/usage"),api("/bills"),api("/slab-breakdowns")
    ]);
    cache={consumers,connections,usage,bills,slabs}; render();
  } catch(error) {
    $("api-status").textContent="Backend / database not connected";
    notify(error.message+" — start Flask and check MySQL settings.",true);
  }
}
function formObject(form) {
  const obj=Object.fromEntries(new FormData(form).entries());
  for(const key of Object.keys(obj)) if(obj[key]==="") obj[key]=null;
  return obj;
}
$("consumer-form").addEventListener("submit", async e => {
  e.preventDefault();
  const form = e.currentTarget;
  try { 
    await api("/consumers", { method: "POST", body: JSON.stringify(formObject(form)) }); 
    form.reset(); 
    await refresh(); 
    notify("Consumer saved to MySQL."); 
  }
  catch(err){ notify(err.message, true); }
});
$("connection-form").addEventListener("submit", async e => {
  e.preventDefault();
  const form = e.currentTarget;
  try {
    const payload = formObject(form);
    console.log("Submitting connection payload:", payload); // Debugging line to check values in F12 console
    
    await api("/connections", { 
      method: "POST", 
      body: JSON.stringify(payload) 
    }); 
    
    form.reset(); 
    await refresh(); 
    notify("Connection saved to MySQL."); 
  } catch(err) { 
    console.error("Connection submission error:", err);
    notify(err.message, true); 
  }
});

$("usage-form").addEventListener("submit", async e => {
  e.preventDefault();
  const form = e.currentTarget;
  try { 
    await api("/usage", { method: "POST", body: JSON.stringify(formObject(form)) }); 
    form.reset(); 
    // Re-apply default date after reset
    $("usage-form").elements.Read_Date.value = new Date().toISOString().slice(0, 10);
    await refresh(); 
    notify("Meter reading saved to MySQL."); 
  }
  catch(err){ notify(err.message, true); }
});

$("bill-form").addEventListener("submit", async e => {
  e.preventDefault();
  const form = e.currentTarget;
  try {
    const bill = await api("/bills", { method: "POST", body: JSON.stringify(formObject(form)) });
    form.reset(); 
    form.elements.Subsidy.value = "0";
    // Re-apply default dates after reset
    form.elements.Bill_Date.value = new Date().toISOString().slice(0, 10);
    const due = new Date(); due.setDate(due.getDate() + 14);
    form.elements.Due_Date.value = due.toISOString().slice(0, 10);

    await refresh();
    // Fixed: Added backticks around the URL
    const detail = await api(`/bills/${bill.Bill_ID}`);
    showBill(detail);
    // Fixed: Added backticks around the notification message string
    notify(`Bill #${bill.Bill_ID} generated. Final amount: ${money(detail.Final_Amount)}.`);
  } catch(err){ notify(err.message, true); }
});
function showBill(bill) {
  const rows=bill.slab_breakdown.map(s=>`<tr><td>${esc(s.Slab_Range)}</td><td>${Number(s.Units_In_Slab).toFixed(2)}</td><td>${money(s.Rate)}</td><td>${money(s.Slab_Amount)}</td></tr>`).join("");
  const win=window.open("","_blank","width=800,height=750");
  if(!win){notify("Allow pop-ups to view/print the generated bill.",true);return;}
  win.document.write(`<!doctype html><html><head><title>Electricity Bill ${bill.Bill_ID}</title><style>body{font:14px Arial;margin:35px;color:#1d2b42}h1{color:#3159c9}table{width:100%;border-collapse:collapse;margin-top:15px}td,th{border:1px solid #ddd;padding:10px;text-align:left}th{background:#f2f5fb}.total{font-size:20px;font-weight:bold}.muted{color:#667085}@media print{button{display:none}}</style></head><body><h1>⚡ VoltCare Electricity Bill</h1><p class="muted">Illustrative academic project tariff — not an official utility bill.</p><hr><p><b>Bill ID:</b> ${bill.Bill_ID} &nbsp; <b>Consumer:</b> ${esc(bill.Consumer_Name)}</p><p><b>Consumer ID:</b> ${bill.Consumer_ID} &nbsp; <b>Connection:</b> ${bill.Connection_ID} &nbsp; <b>Meter:</b> ${esc(bill.Meter_No)}</p><p><b>Bill date:</b> ${esc(bill.Bill_Date)} &nbsp; <b>Due date:</b> ${esc(bill.Due_Date)}</p><p><b>Units consumed:</b> ${Number(bill.Units_Consumed).toFixed(2)} kWh</p><h2>Slab-wise energy charge</h2><table><thead><tr><th>Slab range</th><th>Units</th><th>Rate per unit</th><th>Amount</th></tr></thead><tbody>${rows}</tbody></table><table><tbody><tr><td>Energy charge</td><td colspan="3">${money(bill.Energy_Charge)}</td></tr><tr><td>Subsidy</td><td colspan="3">− ${money(bill.Subsidy)}</td></tr><tr><td class="total">Final amount</td><td colspan="3" class="total">${money(bill.Final_Amount)}</td></tr><tr><td>Payment status</td><td colspan="3">${esc(bill.Payment_Status)}</td></tr></tbody></table><p class="muted">The final amount is calculated by the backend and stored in MySQL along with the slab breakdown.</p><button onclick="window.print()">Print / Save as PDF</button></body></html>`);
  win.document.close();
}
$("refresh").addEventListener("click",refresh);
document.addEventListener("click",async e=>{
  const button=e.target.closest("[data-paid]"); if(!button)return;
  try{await api(`/bills/${button.dataset.paid}/payment`,{method:"PATCH",body:JSON.stringify({Payment_Status:"Paid"})});await refresh();notify("Payment status updated.");}
  catch(err){notify(err.message,true);}
});
const today=new Date().toISOString().slice(0,10);
$("usage-form").elements.Read_Date.value=today;
$("bill-form").elements.Bill_Date.value=today;
const due=new Date();due.setDate(due.getDate()+14);$("bill-form").elements.Due_Date.value=due.toISOString().slice(0,10);
refresh();
