/* TOGGLE CONTRASEÑA */
function togglePassword(inputId,toggleId){
const toggle=document.getElementById(toggleId);
const password=document.getElementById(inputId);

toggle.addEventListener("click",()=>{
const type=password.getAttribute("type")==="password"?"text":"password";
password.setAttribute("type",type);
toggle.classList.toggle("fa-eye");
toggle.classList.toggle("fa-eye-slash");
});
}

togglePassword("password","togglePassword");
togglePassword("confirmPassword","togglePassword2");

/* MENSAJES AUTOMATICOS 3 SEGUNDOS */
setTimeout(()=>{
const flashes=document.querySelectorAll(".flash");
flashes.forEach(f=>{
f.style.transition="opacity 0.5s";
f.style.opacity="0";
setTimeout(()=>f.remove(),500);
});
},3000);