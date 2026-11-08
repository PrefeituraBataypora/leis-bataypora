// Acrescenta, ao lado do lápis (editar), um botão que abre no GitHub o histórico de
// alterações do arquivo da página. O endereço sai do próprio link de edição:
// .../edit/main/docs/<arquivo>.md  ->  .../commits/main/docs/<arquivo>.md
(function () {
  var ICONE =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M13.5 8H12v5l4.28 ' +
    "2.54.72-1.21-3.5-2.08zM13 3a9 9 0 0 0-9 9H1l3.96 4.03L9 12H6a7 7 0 0 1 7-7 7 7 0 0 1 7 " +
    "7 7 7 0 0 1-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42A8.9 8.9 0 0 0 13 21a9 9 0 0 0 9-9 " +
    '9 9 0 0 0-9-9"/></svg>';

  function adicionar() {
    var editar = document.querySelector('a.md-content__button[href*="/edit/"]');
    if (!editar || document.querySelector(".botao-historico")) return;
    var botao = document.createElement("a");
    botao.href = editar.href.replace("/edit/", "/commits/");
    botao.title = "Histórico de alterações desta página";
    botao.className = "md-content__button md-icon botao-historico";
    botao.innerHTML = ICONE;
    editar.parentNode.insertBefore(botao, editar);
  }

  if (window.document$ && window.document$.subscribe) {
    window.document$.subscribe(adicionar);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", adicionar);
  } else {
    adicionar();
  }
})();
