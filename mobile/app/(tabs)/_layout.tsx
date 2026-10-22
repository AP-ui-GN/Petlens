import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import { Image, Text, View } from 'react-native';

import { useColors } from '../../src/theme-context';

function PetLensHeader() {
  const colors = useColors();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 9 }}>
      <Image
        accessibilityLabel="PetLens analysis for dogs"
        source={require('../../assets/petlens-dog-mark.png')}
        style={{ width: 34, height: 34, borderRadius: 9, backgroundColor: '#fff' }}
      />
      <View>
        <Text style={{ color: colors.text, fontSize: 16, fontWeight: '800' }}>PetLens</Text>
        <Text style={{ color: colors.muted, fontSize: 9, letterSpacing: 1.1 }}>ANALYSIS FOR DOGS</Text>
      </View>
    </View>
  );
}

export default function TabsLayout() {
  const colors = useColors();
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.background },
        headerShadowVisible: false,
        headerTintColor: colors.text,
        headerTitleStyle: { fontWeight: '700' },
        headerTitle: PetLensHeader,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { backgroundColor: colors.card, borderTopColor: colors.border, minHeight: 56 },
        sceneStyle: { backgroundColor: colors.background },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, size }) => <Ionicons name="home-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="analyze"
        options={{
          title: 'Analyze',
          tabBarIcon: ({ color, size }) => <Ionicons name="videocam-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'History',
          tabBarIcon: ({ color, size }) => <Ionicons name="time-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarIcon: ({ color, size }) => <Ionicons name="settings-outline" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
