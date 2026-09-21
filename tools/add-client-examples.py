#!/usr/bin/env python3
"""
Inject OpenSearch client code samples (`x-codeSamples`) into every operation of
a built spec.

Scalar auto-generates GENERIC HTTP-client snippets (requests, axios, okhttp, ...)
that have nothing to do with OpenSearch. This pass replaces that with a curated,
uniform set of samples that use each OFFICIAL OpenSearch client library's
low-level transport escape hatch -- the one call that works for ANY endpoint
given (method, path, body). index.html sets `hiddenClients: true`, so the
generated snippets are hidden and only these custom samples render.

Low-level (not idiomatic) is deliberate: a single mechanical template per client
covers all ~700 operations. The high-level clients expose typed helpers
(client.search(...), client.indices.create(...)) but there is no per-operation
mapping here -- the transport call is uniform and always correct.

Languages == the distributions' official clients (opensearch.org/docs/latest/clients):
curl (raw REST), Python, JavaScript/Node, Java, Go, Ruby, PHP, C# (.NET), Rust.
Every transport signature below was verified against the client's source.
"""
import json
import re
import sys

HTTP_METHODS = ('get', 'post', 'put', 'delete', 'head', 'patch')

# Example values substituted for `{path_param}` placeholders so the sample paths
# look like real requests. Unknown params fall back to the param name itself.
PATH_PARAM_EXAMPLES = {
    'index': 'my-index',
    'id': '1',
    'name': 'my-name',
    'repository': 'my-repo',
    'snapshot': 'my-snapshot',
    'target': 'my-target',
    'alias': 'my-alias',
    'field': 'my-field',
    'policy_id': 'my-policy',
    'task_id': 'task-1',
}

# Placeholder request body. We do not synthesize a per-operation body (that is
# the idiomatic-samples project); a POST/PUT shows an empty JSON object the
# reader replaces with their payload.
BODY_NOTE = 'replace with your request body'


def example_path(path):
    """`/{index}/_search` -> `/my-index/_search`."""
    return re.sub(r'\{([^}]+)\}',
                  lambda m: PATH_PARAM_EXAMPLES.get(m.group(1), m.group(1)),
                  path)


# --- Per-client renderers -------------------------------------------------
# Each takes (method, path, has_body) -> source string. `method` is upper-case
# (e.g. "POST"); `path` is the concrete example path; `has_body` says whether
# the operation declares a requestBody.

def curl_sample(method, path, has_body):
    body = (" \\\n  -H 'Content-Type: application/json' \\\n"
            f"  -d '{{}}'  # {BODY_NOTE}") if has_body else ""
    return (f"curl -X {method} 'https://localhost:9200{path}' \\\n"
            f"  -u admin:admin -k{body}")


def python_sample(method, path, has_body):
    # opensearch-py: client.transport.perform_request(method, url, params, body, ...)
    body = f'\n    body={{}},  # {BODY_NOTE}' if has_body else ''
    return (
        'from opensearchpy import OpenSearch\n\n'
        'client = OpenSearch(\n'
        '    hosts=[{"host": "localhost", "port": 9200}],\n'
        '    http_auth=("admin", "admin"),\n'
        '    use_ssl=True,\n'
        '    verify_certs=False,\n'
        ')\n\n'
        'response = client.transport.perform_request(\n'
        f'    method="{method}",\n'
        f'    url="{path}",{body}\n'
        ')\n'
        'print(response)'
    )


def js_sample(method, path, has_body):
    # opensearch-js: client.transport.request({ method, path, querystring, body })
    body = f'\n  body: {{}},  // {BODY_NOTE}' if has_body else ''
    return (
        'const { Client } = require("@opensearch-project/opensearch");\n\n'
        'const client = new Client({\n'
        '  node: "https://admin:admin@localhost:9200",\n'
        '  ssl: { rejectUnauthorized: false },\n'
        '});\n\n'
        'const response = await client.transport.request({\n'
        f'  method: "{method}",\n'
        f'  path: "{path}",{body}\n'
        '});\n'
        'console.log(response.body);'
    )


def java_sample(method, path, has_body):
    # Low-level org.opensearch.client.RestClient (opensearch-rest-client artifact).
    body = (f'\nrequest.setJsonEntity("{{}}");  // {BODY_NOTE}') if has_body else ''
    return (
        'import org.apache.http.HttpHost;\n'
        'import org.apache.http.auth.AuthScope;\n'
        'import org.apache.http.auth.UsernamePasswordCredentials;\n'
        'import org.apache.http.impl.client.BasicCredentialsProvider;\n'
        'import org.apache.http.util.EntityUtils;\n'
        'import org.opensearch.client.Request;\n'
        'import org.opensearch.client.Response;\n'
        'import org.opensearch.client.RestClient;\n\n'
        'BasicCredentialsProvider creds = new BasicCredentialsProvider();\n'
        'creds.setCredentials(AuthScope.ANY,\n'
        '    new UsernamePasswordCredentials("admin", "admin"));\n\n'
        'RestClient restClient = RestClient\n'
        '    .builder(new HttpHost("localhost", 9200, "https"))\n'
        '    .setHttpClientConfigCallback(cb -> cb.setDefaultCredentialsProvider(creds))\n'
        '    .build();\n\n'
        f'Request request = new Request("{method}", "{path}");{body}\n'
        'Response response = restClient.performRequest(request);\n'
        'System.out.println(EntityUtils.toString(response.getEntity()));'
    )


def go_sample(method, path, has_body):
    # opensearch-go v2: client.Perform(*http.Request). v4/main renames it to
    # client.Request(*http.Request) -- noted inline.
    imports = ['\t"crypto/tls"', '\t"net/http"']
    if has_body:
        imports.append('\t"strings"')
    imports.append('\n\t"github.com/opensearch-project/opensearch-go/v2"')
    body_arg = 'strings.NewReader(`{}`)' if has_body else 'nil'
    ctype = ('\nreq.Header.Set("Content-Type", "application/json")  // '
             + BODY_NOTE) if has_body else ''
    return (
        'import (\n' + '\n'.join(imports) + '\n)\n\n'
        'client, _ := opensearch.NewClient(opensearch.Config{\n'
        '    Addresses: []string{"https://localhost:9200"},\n'
        '    Username:  "admin",\n'
        '    Password:  "admin",\n'
        '    Transport: &http.Transport{\n'
        '        TLSClientConfig: &tls.Config{InsecureSkipVerify: true},\n'
        '    },\n'
        '})\n\n'
        f'req, _ := http.NewRequest("{method}", "{path}", {body_arg}){ctype}\n'
        'resp, _ := client.Perform(req)  // opensearch-go v4/main: client.Request(req)\n'
        'defer resp.Body.Close()'
    )


def ruby_sample(method, path, has_body):
    # opensearch-ruby: client.perform_request(method, path, params = {}, body = nil)
    body = f',\n  {{}}  # {BODY_NOTE}' if has_body else ''
    params = ',\n  {}' if has_body else ''
    return (
        'require "opensearch"\n\n'
        'client = OpenSearch::Client.new(\n'
        '  host: "https://admin:admin@localhost:9200",\n'
        '  transport_options: { ssl: { verify: false } }\n'
        ')\n\n'
        'response = client.perform_request(\n'
        f'  "{method}",\n'
        f'  "{path}"{params}{body}\n'
        ')\n'
        'puts response.body'
    )


def php_sample(method, path, has_body):
    # opensearch-php (2.3+ PSR client): $client->request(method, uri, attributes).
    # NB: an empty JSON object must be (object) [], not [] (which encodes as []).
    attrs = (f" [\n    'body' => (object) [],  // {BODY_NOTE}\n]"
             if has_body else '')
    return (
        "require 'vendor/autoload.php';\n\n"
        "$client = (new \\OpenSearch\\GuzzleClientFactory())->create([\n"
        "    'base_uri' => 'https://localhost:9200',\n"
        "    'auth'     => ['admin', 'admin'],\n"
        "    'verify'   => false,\n"
        "]);\n\n"
        f"$response = $client->request('{method}', '{path}'{',' + attrs if attrs else ''});\n"
        "print_r($response);"
    )


def csharp_sample(method, path, has_body):
    # OpenSearch.Net low-level: client.DoRequest<StringResponse>(HttpMethod, path, PostData?)
    # The `;` terminator must precede the trailing comment, else it is commented out.
    body = (f',\n    PostData.String("{{}}"));  // {BODY_NOTE}'
            if has_body else ');')
    return (
        'using OpenSearch.Net;\n\n'
        'var pool = new SingleNodeConnectionPool(new Uri("https://localhost:9200"));\n'
        'var settings = new ConnectionConfiguration(pool)\n'
        '    .BasicAuthentication("admin", "admin")\n'
        '    .ServerCertificateValidationCallback((o, cert, chain, errors) => true);\n\n'
        'var client = new OpenSearchLowLevelClient(settings);\n\n'
        'var response = client.DoRequest<StringResponse>(\n'
        f'    HttpMethod.{method},\n'
        f'    "{path}"{body}\n'
        'Console.WriteLine(response.Body);'
    )


def rust_sample(method, path, has_body):
    # opensearch-rs: client.send(method, path, headers, query, body, timeout).
    # Method is PascalCase (Method::Post). Body: Some(String) or None::<String>.
    m = method.capitalize()  # POST -> Post
    body = (f'Some(r#"{{}}"#),  // {BODY_NOTE}' if has_body else 'None::<String>,')
    return (
        'use opensearch::{\n'
        '    OpenSearch,\n'
        '    auth::Credentials,\n'
        '    cert::CertificateValidation,\n'
        '    http::{Method, headers::HeaderMap,\n'
        '        transport::{SingleNodeConnectionPool, TransportBuilder}},\n'
        '};\n'
        'use url::Url;\n\n'
        'let pool = SingleNodeConnectionPool::new(Url::parse("https://localhost:9200")?);\n'
        'let transport = TransportBuilder::new(pool)\n'
        '    .auth(Credentials::Basic("admin".into(), "admin".into()))\n'
        '    .cert_validation(CertificateValidation::None)\n'
        '    .build()?;\n'
        'let client = OpenSearch::new(transport);\n\n'
        'let response = client.send(\n'
        f'    Method::{m},\n'
        f'    "{path}",\n'
        '    HeaderMap::new(),\n'
        '    Option::<&()>::None,\n'
        f'    {body}\n'
        '    None,\n'
        ').await?;'
    )


CLIENTS = [
    # (lang-for-highlight, label-in-picker, renderer)
    ('bash', 'curl', curl_sample),
    ('python', 'Python (opensearch-py)', python_sample),
    ('javascript', 'JavaScript (opensearch-js)', js_sample),
    ('java', 'Java (opensearch-java)', java_sample),
    ('go', 'Go (opensearch-go)', go_sample),
    ('ruby', 'Ruby (opensearch-ruby)', ruby_sample),
    ('php', 'PHP (opensearch-php)', php_sample),
    ('csharp', 'C# (OpenSearch.Net)', csharp_sample),
    ('rust', 'Rust (opensearch-rs)', rust_sample),
]


def build_samples(method, path, has_body):
    concrete = example_path(path)
    return [
        {'lang': lang, 'label': label, 'source': render(method, concrete, has_body)}
        for lang, label, render in CLIENTS
    ]


def process_spec(spec):
    count = 0
    for path, methods in spec.get('paths', {}).items():
        if not isinstance(methods, dict):
            continue
        for method in list(methods.keys()):
            if method not in HTTP_METHODS:
                continue
            op = methods[method]
            if not isinstance(op, dict):
                continue
            has_body = isinstance(op.get('requestBody'), dict)
            op['x-codeSamples'] = build_samples(method.upper(), path, has_body)
            count += 1
    return count


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 1:
        print(f"Usage: {sys.argv[0]} <spec.json> [output.json]  "
              f"(in-place if no output given)")
        sys.exit(1)
    src = args[0]
    dst = args[1] if len(args) > 1 else src

    with open(src) as f:
        spec = json.load(f)

    n = process_spec(spec)

    with open(dst, 'w') as f:
        json.dump(spec, f)

    print(f"  x-codeSamples: injected {len(CLIENTS)} client samples "
          f"into {n} operations -> {dst}")
