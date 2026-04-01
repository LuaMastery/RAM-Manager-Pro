# RAM Manager Pro - Site Oficial

Este é o site oficial do **RAM Manager Pro**, hospedado no GitHub Pages.

## 📋 Estrutura do Site

```
docs/
├── index.html      # Página principal
├── styles.css      # Estilos CSS
├── script.js       # Scripts JavaScript
└── README.md       # Este arquivo
```

## 🚀 Como Configurar o GitHub Pages

1. **Crie um repositório no GitHub**
   - Nome: `ram-manager-pro`
   - Visibilidade: Pública

2. **Faça upload dos arquivos**
   - Coloque todos os arquivos da pasta `docs/` na raiz do repositório
   - Ou crie uma pasta `docs/` e coloque os arquivos lá

3. **Ative o GitHub Pages**
   - Vá em **Settings** → **Pages**
   - Em "Source", selecione:
     - **Deploy from a branch**
     - Branch: `main` (ou `master`)
     - Pasta: `/docs` (ou `/root` se estiver na raiz)
   - Clique em **Save**

4. **Acesse o site**
   - URL será: `https://seuusuario.github.io/ram-manager-pro/`
   - Pode levar até 10 minutos para propagar

## 🎨 Características do Site

- ✅ Design moderno e responsivo
- ✅ Animações suaves e interativas
- ✅ Seção de download com instruções
- ✅ Histórico de versões
- ✅ Guia de funcionalidades
- ✅ Totalmente estático (HTML/CSS/JS)

## 📝 Personalização

### Alterar links de download
No arquivo `index.html`, procure por:
```html
<a href="https://github.com/seuusuario/ram-manager-pro/releases/download/v2.0/ram-manager-pro-v2.0.zip" ...>
```

Substitua pelo link real do release.

### Alterar cores
Edite as variáveis CSS em `styles.css`:
```css
:root {
    --primary-color: #6366f1;
    --secondary-color: #06b6d4;
    ...
}
```

## 🔗 Links Importantes

- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [Custom Domain Setup](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site)

---

© 2026 RAM Manager Pro - Todos os direitos reservados.
