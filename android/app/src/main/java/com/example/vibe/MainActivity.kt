package com.example.vibe

import android.Manifest
import android.app.AlertDialog
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.ContentValues
import android.content.Context
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.MediaStore
import android.util.Log
import android.view.View
import android.webkit.URLUtil
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.InputStream
import java.io.OutputStream
import java.util.concurrent.TimeUnit

class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var prefs: SharedPreferences
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(60, TimeUnit.SECONDS)
        .readTimeout(300, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    companion object {
        private const val REQUEST_CODE_PERMISSIONS = 101
        private const val TAG = "VibeApp"
        private const val CHANNEL_ID = "vibe_downloads"
        private const val DEFAULT_URL = "http://127.0.0.1:8080/"
        private const val PREF_KEY_URL = "server_url"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        prefs = getPreferences(Context.MODE_PRIVATE)
        webView = findViewById(R.id.webView)
        progressBar = findViewById(R.id.progressBar)

        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null)
        webView.setBackgroundColor(android.graphics.Color.TRANSPARENT)

        createNotificationChannel()
        checkPermissions()
        setupWebView()
        
        val savedUrl = prefs.getString(PREF_KEY_URL, DEFAULT_URL) ?: DEFAULT_URL
        Log.d(TAG, "Loading Vibe UI: $savedUrl")
        webView.loadUrl(savedUrl)

        webView.setOnLongClickListener {
            showUrlDialog()
            true
        }
    }

    private fun showUrlDialog() {
        val builder = AlertDialog.Builder(this)
        builder.setTitle("Server Settings")
        
        val currentUrl = prefs.getString(PREF_KEY_URL, DEFAULT_URL)
        builder.setMessage("Current URL: $currentUrl\n\nType a new URL to connect to a different server.")

        val input = EditText(this)
        input.setText(currentUrl)
        builder.setView(input)

        builder.setPositiveButton("Connect") { _, _ ->
            var newUrl = input.text.toString().trim()
            if (newUrl.isNotEmpty()) {
                if (!newUrl.startsWith("http")) newUrl = "http://$newUrl"
                if (!newUrl.endsWith("/")) newUrl = "$newUrl/"
                prefs.edit().putString(PREF_KEY_URL, newUrl).apply()
                webView.loadUrl(newUrl)
                Toast.makeText(this, "Switched to $newUrl", Toast.LENGTH_SHORT).show()
            }
        }
        
        builder.setNeutralButton("Reset to Local") { _, _ ->
            prefs.edit().putString(PREF_KEY_URL, DEFAULT_URL).apply()
            webView.loadUrl(DEFAULT_URL)
            Toast.makeText(this, "Reset to $DEFAULT_URL", Toast.LENGTH_SHORT).show()
        }

        builder.setNegativeButton("Cancel") { dialog, _ -> dialog.cancel() }
        builder.show()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val name = "Downloads"
            val channel = NotificationChannel(CHANNEL_ID, name, NotificationManager.IMPORTANCE_LOW)
            val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun checkPermissions() {
        val permissions = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            permissions.add(Manifest.permission.WRITE_EXTERNAL_STORAGE)
        }
        val needed = permissions.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (needed.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, needed.toTypedArray(), REQUEST_CODE_PERMISSIONS)
        }
    }

    private fun setupWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            loadWithOverviewMode = true
            useWideViewPort = true
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        }

        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                progressBar.visibility = View.VISIBLE
            }
            override fun onPageFinished(view: WebView?, url: String?) {
                progressBar.visibility = View.GONE
            }
            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                if (request?.isForMainFrame == true) {
                    Log.e(TAG, "Load Error: ${error?.description}")
                    if (error?.errorCode == -6) { // Connection refused
                         Toast.makeText(this@MainActivity, "Server not found. Is Termux running?", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                progressBar.progress = newProgress
                if (newProgress == 100) progressBar.visibility = View.GONE
            }
        }

        webView.setDownloadListener { url, _, contentDisposition, mimetype, _ ->
            val fileName = URLUtil.guessFileName(url, contentDisposition, mimetype)
            startManualDownload(url, fileName)
        }
    }

    private fun startManualDownload(url: String, fileName: String) {
        Toast.makeText(this, "Starting Download...", Toast.LENGTH_SHORT).show()
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val notificationBuilder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle(fileName)
            .setContentText("Downloading from internal server...")
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .setProgress(100, 0, true)

        val notificationId = (System.currentTimeMillis() % 10000).toInt()
        notificationManager.notify(notificationId, notificationBuilder.build())

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val request = Request.Builder().url(url).build()
                val response = client.newCall(request).execute()
                if (!response.isSuccessful) throw Exception("Server error ${response.code}")
                
                val body = response.body ?: throw Exception("Body is empty")
                val totalBytes = body.contentLength()
                val inputStream: InputStream = body.byteStream()
                
                val outputStream: OutputStream = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    val contentValues = ContentValues().apply {
                        put(MediaStore.MediaColumns.DISPLAY_NAME, fileName)
                        put(MediaStore.MediaColumns.MIME_TYPE, response.header("Content-Type") ?: "audio/mpeg")
                        put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                    }
                    val uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)
                        ?: throw Exception("Storage Error")
                    contentResolver.openOutputStream(uri) ?: throw Exception("Write Error")
                } else {
                    val file = java.io.File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), fileName)
                    java.io.FileOutputStream(file)
                }

                val buffer = ByteArray(65536)
                var bytesRead: Int
                var totalRead: Long = 0
                var lastUpdate: Long = 0
                
                outputStream.use { out ->
                    while (inputStream.read(buffer).also { bytesRead = it } != -1) {
                        out.write(buffer, 0, bytesRead)
                        totalRead += bytesRead
                        val now = System.currentTimeMillis()
                        if (now - lastUpdate > 1000 && totalBytes > 0) {
                            val progress = (totalRead * 100 / totalBytes).toInt()
                            notificationBuilder.setProgress(100, progress, false).setContentText("$progress% Downloaded")
                            notificationManager.notify(notificationId, notificationBuilder.build())
                            lastUpdate = now
                        }
                    }
                }

                withContext(Dispatchers.Main) {
                    notificationBuilder.setContentText("Complete").setSmallIcon(android.R.drawable.stat_sys_download_done)
                        .setOngoing(false).setProgress(0, 0, false)
                    notificationManager.notify(notificationId, notificationBuilder.build())
                    Toast.makeText(this@MainActivity, "Saved to Downloads", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    notificationBuilder.setContentText("Failed: ${e.message}").setOngoing(false).setProgress(0, 0, false)
                    notificationManager.notify(notificationId, notificationBuilder.build())
                    Toast.makeText(this@MainActivity, "Error: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }
}
