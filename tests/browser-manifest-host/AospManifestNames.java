/*
 * Copyright (C) 2022 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

// Exact method excerpts from AOSP android-15.0.0_r1 PackageParser.java.
// Host execution of name grammar only; this is not Android PackageManager.
public final class AospManifestNames {
public static String validateName(String name, boolean requireSeparator,
            boolean requireFilename) {
        final int N = name.length();
        boolean hasSep = false;
        boolean front = true;
        for (int i=0; i<N; i++) {
            final char c = name.charAt(i);
            if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')) {
                front = false;
                continue;
            }
            if (!front) {
                if ((c >= '0' && c <= '9') || c == '_') {
                    continue;
                }
            }
            if (c == '.') {
                hasSep = true;
                front = true;
                continue;
            }
            return "bad character '" + c + "'";
        }
        if (requireFilename && !FileUtils.isValidExtFilename(name)) {
            return "Invalid filename";
        }
        return hasSep || !requireSeparator
                ? null : "must have at least one '.' separator";
    }

private static String buildCompoundName(String pkg,
            CharSequence procSeq, String type, String[] outError) {
        String proc = procSeq.toString();
        char c = proc.charAt(0);
        if (pkg != null && c == ':') {
            if (proc.length() < 2) {
                outError[0] = "Bad " + type + " name " + proc + " in package " + pkg
                        + ": must be at least two characters";
                return null;
            }
            String subName = proc.substring(1);
            String nameError = validateName(subName, false, false);
            if (nameError != null) {
                outError[0] = "Invalid " + type + " name " + proc + " in package "
                        + pkg + ": " + nameError;
                return null;
            }
            return pkg + proc;
        }
        String nameError = validateName(proc, true, false);
        if (nameError != null && !"system".equals(proc)) {
            outError[0] = "Invalid " + type + " name " + proc + " in package "
                    + pkg + ": " + nameError;
            return null;
        }
        return proc;
    }

public static String buildTaskAffinityName(String pkg, String defProc,
            CharSequence procSeq, String[] outError) {
        if (procSeq == null) {
            return defProc;
        }
        if (procSeq.length() <= 0) {
            return null;
        }
        return buildCompoundName(pkg, procSeq, "taskAffinity", outError);
    }

    public static String process(String pkg, String value, String[] error) {
        return buildCompoundName(pkg, value, "process", error);
    }
    public static void main(String[] args) throws Exception {
        for (String row : java.nio.file.Files.readAllLines(java.nio.file.Paths.get(args[0]), java.nio.charset.StandardCharsets.UTF_8)) {
            String[] fields = row.split("\t", -1);
            if (fields.length != 3) throw new AssertionError("Invalid explicit name case");
            String[] error = {null};
            if (fields[0].equals("package")) error[0] = validateName(fields[2], true, false);
            else if (fields[0].equals("taskAffinity")) buildTaskAffinityName(fields[1], fields[1], fields[2], error);
            else if (fields[0].equals("process")) process(fields[1], fields[2], error);
            else throw new AssertionError("Unknown explicit name case");
            System.out.println(error[0] == null ? "VALID" : "INVALID:" + error[0]);
        }
    }
}
/** Explicit unused boundary: all task/process callers pass requireFilename=false. */
final class FileUtils {
    static boolean isValidExtFilename(String name) {
        throw new AssertionError("Filename validation is outside this host name-grammar test");
    }
}
