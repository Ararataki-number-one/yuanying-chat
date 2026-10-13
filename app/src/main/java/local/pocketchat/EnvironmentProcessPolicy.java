package local.pocketchat;

/** A slot number alone does not identify its owner process: maintenance and
 * integration processes also have no :profile suffix and otherwise look like slot zero. */
final class EnvironmentProcessPolicy {
  static boolean owns(String packageName,String processName,int slot){
    return slot>=0&&slot<8&&packageName!=null&&processName!=null
        &&processName.equals(packageName+(slot==0?"":":profile"+slot));
  }
}
