// ChatView.swift
// The main chat interface — messages, input bar, document upload, PDF viewer, and knowledge graph.

import SwiftUI
import Combine
import UniformTypeIdentifiers
import WebKit

struct ChatView: View {
    @StateObject private var viewModel = ChatViewModel()
    @State private var showDocumentPicker = false
    @State private var showDocumentList = false
    @State private var showKnowledgeGraph = false
    @State private var pdfURL: URL? = nil
    @State private var pdfTitle: String = ""

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // MARK: Processing Banner
                if viewModel.isProcessing {
                    HStack(spacing: 8) {
                        ProgressView()
                            .scaleEffect(0.8)
                        Text(viewModel.processingMessage)
                            .font(.caption)
                            .foregroundColor(.orange)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(8)
                    .background(Color.orange.opacity(0.1))
                }

                // MARK: Message List
                ScrollViewReader { scrollProxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 12) {
                            ForEach(viewModel.messages) { message in
                                MessageBubble(message: message, onRefTap: { filename, url in
                                    pdfTitle = filename
                                    pdfURL = url
                                })
                                .id(message.id)
                            }

                            if viewModel.isLoading {
                                TypingIndicator()
                                    .id("typing")
                            }
                        }
                        .padding()
                    }
                    .onChange(of: viewModel.messages.count) {
                        if let lastMessage = viewModel.messages.last {
                            withAnimation {
                                scrollProxy.scrollTo(lastMessage.id, anchor: .bottom)
                            }
                        }
                    }
                }

                // MARK: Input Bar
                InputBar(
                    text: $viewModel.inputText,
                    isLoading: viewModel.isLoading,
                    onSend: { viewModel.sendMessage() },
                    onAttach: { showDocumentPicker = true }
                )
            }
            .navigationTitle("Document Assistant")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    HStack(spacing: 12) {
                        Button {
                            showKnowledgeGraph = true
                        } label: {
                            Image(systemName: "point.3.connected.trianglepath.dotted")
                        }
                        Button {
                            viewModel.clearChat()
                        } label: {
                            Image(systemName: "square.and.pencil")
                        }
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    HStack(spacing: 12) {
                        Button {
                            viewModel.saveConversation()
                        } label: {
                            Image(systemName: "square.and.arrow.down")
                        }
                        Button {
                            showDocumentList = true
                        } label: {
                            Image(systemName: "doc.text.magnifyingglass")
                        }
                    }
                }
            }
            .sheet(isPresented: $showDocumentPicker) {
                DocumentPicker { filename, data in
                    viewModel.uploadDocument(filename: filename, data: data)
                }
            }
            .sheet(isPresented: $showDocumentList) {
                DocumentListView(documents: viewModel.uploadedDocuments)
            }
            .fullScreenCover(isPresented: $showKnowledgeGraph) {
                KnowledgeGraphSheet()
            }
            .sheet(item: Binding(
                get: { pdfURL.map { IdentifiableURL(url: $0, title: pdfTitle) } },
                set: { pdfURL = $0?.url }
            )) { item in
                PDFViewerSheet(title: item.title, url: item.url)
            }
        }
    }
}

// MARK: - Identifiable URL wrapper

struct IdentifiableURL: Identifiable {
    let id = UUID()
    let url: URL
    let title: String
}

// MARK: - Knowledge Graph Sheet

struct KnowledgeGraphSheet: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            WebView(url: URL(string: "\(APIService.baseURL)/graph-view")!)
                .navigationTitle("Knowledge Graph")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .navigationBarLeading) {
                        Button("Done") { dismiss() }
                    }
                }
        }
    }
}

// MARK: - PDF Viewer Sheet

struct PDFViewerSheet: View {
    let title: String
    let url: URL
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            WebView(url: url)
                .navigationTitle(title)
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .navigationBarLeading) {
                        Button("Done") { dismiss() }
                    }
                }
        }
    }
}

// MARK: - WebKit WebView

struct WebView: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.load(URLRequest(url: url))
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}
}

// MARK: - Message Bubble

struct MessageBubble: View {
    let message: ChatMessage
    var onRefTap: ((String, URL) -> Void)? = nil

    var body: some View {
        HStack {
            if message.isUser { Spacer(minLength: 60) }

            VStack(alignment: message.isUser ? .trailing : .leading, spacing: 4) {
                if message.isUser {
                    Text(message.content)
                        .padding(12)
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(16)
                } else {
                    FormattedMessageView(
                        content: message.content,
                        pdfURLs: message.pdfURLs,
                        onRefTap: onRefTap
                    )
                    .padding(12)
                    .background(Color(.systemGray5))
                    .foregroundColor(.primary)
                    .cornerRadius(16)
                    .contextMenu {
                        Button {
                            UIPasteboard.general.string = message.content
                        } label: {
                            Label("Copy", systemImage: "doc.on.doc")
                        }
                        ShareLink(item: message.content) {
                            Label("Share", systemImage: "square.and.arrow.up")
                        }
                    }
                }

                if !message.sources.isEmpty {
                    HStack(spacing: 4) {
                        ForEach(message.sources, id: \.self) { source in
                            if let pdfPath = message.pdfURLs[source],
                               let url = URL(string: "\(APIService.baseURL)\(pdfPath)") {
                                Button {
                                    onRefTap?(source, url)
                                } label: {
                                    Text("View \(source)")
                                        .font(.caption2)
                                        .foregroundColor(.blue)
                                }
                            } else {
                                Text(source)
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    .padding(.horizontal, 4)
                }
            }

            if !message.isUser { Spacer(minLength: 60) }
        }
    }
}

// MARK: - Formatted Message View (handles ref:// links)

struct FormattedMessageView: View {
    let content: String
    let pdfURLs: [String: String]
    var onRefTap: ((String, URL) -> Void)? = nil

    var body: some View {
        let parts = parseContent(content)
        VStack(alignment: .leading, spacing: 0) {
            Text(buildAttributedText(parts: parts))
                .environment(\.openURL, OpenURLAction { url in
                    if url.scheme == "ref" {
                        let filename = url.host(percentEncoded: false) ?? ""
                        let page = url.pathComponents.count >= 3 ? url.pathComponents[2] : nil
                        if let pdfPath = pdfURLs[filename] {
                            let fullPath = page != nil ? "\(pdfPath)#page=\(page!)" : pdfPath
                            if let pdfURL = URL(string: "\(APIService.baseURL)\(fullPath)") {
                                onRefTap?(filename, pdfURL)
                            }
                        }
                        return .handled
                    }
                    return .systemAction
                })
        }
    }

    enum ContentPart {
        case text(String)
        case link(label: String, filename: String, page: String?)
    }

    func parseContent(_ text: String) -> [ContentPart] {
        var parts: [ContentPart] = []
        let pattern = #"\[([^\]]+)\]\(ref://([^)]+)\)"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else {
            return [.text(text)]
        }

        let nsString = text as NSString
        var lastIndex = 0

        let matches = regex.matches(in: text, range: NSRange(location: 0, length: nsString.length))
        for match in matches {
            let beforeRange = NSRange(location: lastIndex, length: match.range.location - lastIndex)
            if beforeRange.length > 0 {
                parts.append(.text(nsString.substring(with: beforeRange)))
            }

            let label = nsString.substring(with: match.range(at: 1))
            let refPath = nsString.substring(with: match.range(at: 2))

            // Parse filename and page number from ref://FILENAME/page/PAGE_NUMBER
            let pageParts = refPath.components(separatedBy: "/page/")
            let filename = pageParts.first ?? refPath
            let page = pageParts.count > 1 ? pageParts[1] : nil

            parts.append(.link(label: label, filename: filename, page: page))
            lastIndex = match.range.location + match.range.length
        }

        if lastIndex < nsString.length {
            parts.append(.text(nsString.substring(from: lastIndex)))
        }

        return parts
    }

    func buildAttributedText(parts: [ContentPart]) -> AttributedString {
        var result = AttributedString()
        for part in parts {
            switch part {
            case .text(let str):
                result += AttributedString(str)
            case .link(let label, let filename, let page):
                var linkStr = AttributedString(label)
                linkStr.foregroundColor = .blue
                linkStr.underlineStyle = .single
                let refString = page != nil ? "ref://\(filename)/page/\(page!)" : "ref://\(filename)"
                if let url = URL(string: refString) {
                    linkStr.link = url
                }
                result += linkStr
            }
        }
        return result
    }
}

// MARK: - Typing Indicator

struct TypingIndicator: View {
    @State private var dotCount = 0
    let timer = Timer.publish(every: 0.4, on: .main, in: .common).autoconnect()

    var body: some View {
        HStack {
            Text("Thinking" + String(repeating: ".", count: dotCount))
                .foregroundColor(.secondary)
                .padding(12)
                .background(Color(.systemGray5))
                .cornerRadius(16)
                .onReceive(timer) { _ in
                    dotCount = (dotCount + 1) % 4
                }
            Spacer()
        }
    }
}

// MARK: - Input Bar

struct InputBar: View {
    @Binding var text: String
    let isLoading: Bool
    let onSend: () -> Void
    let onAttach: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            Divider()
            HStack(spacing: 12) {
                Button(action: onAttach) {
                    Image(systemName: "paperclip")
                        .font(.title3)
                        .foregroundColor(.blue)
                }

                TextField("Ask about your documents...", text: $text, axis: .vertical)
                    .textFieldStyle(.plain)
                    .lineLimit(1...5)
                    .padding(10)
                    .background(Color(.systemGray6))
                    .cornerRadius(20)

                Button(action: onSend) {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.title2)
                        .foregroundColor(
                            text.trimmingCharacters(in: .whitespaces).isEmpty || isLoading
                                ? .gray : .blue
                        )
                }
                .disabled(text.trimmingCharacters(in: .whitespaces).isEmpty || isLoading)
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
        }
        .background(Color(.systemBackground))
    }
}

// MARK: - Document Picker

struct DocumentPicker: UIViewControllerRepresentable {
    let onPick: (String, Data) -> Void

    func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
        let types: [UTType] = [.pdf, .plainText, .text, .utf8PlainText]
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: types)
        picker.delegate = context.coordinator
        picker.allowsMultipleSelection = false
        return picker
    }

    func updateUIViewController(_ uiViewController: UIDocumentPickerViewController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(onPick: onPick)
    }

    class Coordinator: NSObject, UIDocumentPickerDelegate {
        let onPick: (String, Data) -> Void
        init(onPick: @escaping (String, Data) -> Void) { self.onPick = onPick }

        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            guard let url = urls.first else { return }
            guard url.startAccessingSecurityScopedResource() else { return }
            defer { url.stopAccessingSecurityScopedResource() }
            if let data = try? Data(contentsOf: url) {
                onPick(url.lastPathComponent, data)
            }
        }
    }
}

// MARK: - Document List View

struct DocumentListView: View {
    let documents: [DocumentInfo]

    var body: some View {
        NavigationView {
            List {
                if documents.isEmpty {
                    Text("No documents uploaded yet.\nUse the paperclip button to add documents.")
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .listRowBackground(Color.clear)
                } else {
                    ForEach(documents, id: \.filename) { doc in
                        HStack {
                            Image(systemName: "doc.text")
                                .foregroundColor(.blue)
                            VStack(alignment: .leading) {
                                Text(doc.filename)
                                    .font(.body)
                                Text("\(doc.characters.formatted()) characters\(doc.pageCount > 0 ? " · \(doc.pageCount) pages" : "")")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Loaded Documents")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
