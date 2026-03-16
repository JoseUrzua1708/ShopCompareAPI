    const modal = document.getElementById("docModal");
    const btn = document.querySelector(".doc-btn");
    const span = document.querySelector(".close-btn");

    btn.onclick = (e) => { e.preventDefault(); modal.style.display = "block"; }
    span.onclick = () => { modal.style.display = "none"; }
    window.onclick = (event) => { if (event.target == modal) modal.style.display = "none"; }

function copyToClipboard(element) {
    const text = element.textContent.trim();
    navigator.clipboard.writeText(text).then(() => {
        const originalTooltip = element.getAttribute("data-tooltip");
        element.setAttribute("data-tooltip", "¡Copiado!");
        setTimeout(() => {
            element.setAttribute("data-tooltip", originalTooltip);
        }, 1500);
    });
}