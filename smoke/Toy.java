// Toy Java program for S0 smoke test
// Prints Java version and exits with code 0

public class Toy {
    public static void main(String[] args) {
        String version = System.getProperty("java.version");
        System.out.println("Java version: " + version);
        System.exit(0);
    }
}
