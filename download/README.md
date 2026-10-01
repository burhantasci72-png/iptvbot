# Vercel HTTPS indirme sayfası

`/scanner/` uygulaması, oluşturulan TXT/M3U çıktısını Base64 olarak URL fragment'ına koyarak gerçek HTTPS bağlantısı açar:

```text
https://iptvbot-t6zv.vercel.app/download/?type=txt&name=iptv_hitler.txt#...
```

`/download/index.html` fragment'ı çözer, tarayıcı içinde Blob oluşturur ve dosyayı indirir. Veriler sunucuya POST edilmez veya GitHub'a yazılmaz.

## Vercel

GitHub deposu Vercel'e bağlandıktan sonra root directory boş bırakılmalıdır. Her push sonrası şu adresler yayınlanır:

- Uygulama: `/scanner/`
- İndirme sayfası: `/download/`

URL fragment'ı sunucuya gönderilmediği için çıktı geçici olarak yalnızca tarayıcıda işlenir.
