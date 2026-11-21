// SPDX-License-Identifier: Apache-2.0
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

class Healthcheck {
    public static void main(String[] args) throws Exception {
        String host = System.getenv().getOrDefault("CRM_PUBLIC_HOST", "bhashcrm.bhashitva.org");
        var request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:8080/healthz"))
                .timeout(Duration.ofSeconds(4)).header("Host", host).GET().build();
        var client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
        System.exit(client.send(request, HttpResponse.BodyHandlers.discarding()).statusCode() == 200 ? 0 : 1);
    }
}
